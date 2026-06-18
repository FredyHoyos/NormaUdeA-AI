from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable
from pathlib import Path
from urllib.parse import urlparse

import fitz
import pytesseract
import requests
from PIL import Image

from app.config.settings import Settings
from app.domain.document_source import DocumentSource
from app.ingestion.chunking import chunk_text
from app.models import DocumentChunk, IngestionProgress, IngestionSummary, RetrievalHit
from app.vectorstore.chroma_store import ChromaKnowledgeBase

logger = logging.getLogger(__name__)


class UdeaPortalSource(DocumentSource):
    """Fuente documental basada en tabla Supabase con URLs de PDF."""

    def __init__(self, settings: Settings, knowledge_base: ChromaKnowledgeBase) -> None:
        self.settings = settings
        self.knowledge_base = knowledge_base

    @staticmethod
    def _stable_chunk_id(source_key: str, page_number: int, chunk_index: int, text: str) -> str:
        digest = hashlib.sha1(f"{source_key}:{page_number}:{chunk_index}:{text}".encode("utf-8")).hexdigest()
        return digest[:24]

    @staticmethod
    def _extract_page_text_with_ocr(page: fitz.Page, ocr_lang: str) -> str:
        matrix = fitz.Matrix(2.0, 2.0)
        pix = page.get_pixmap(matrix=matrix, alpha=False)
        image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        return pytesseract.image_to_string(image, lang=ocr_lang).strip()

    def _build_source_name(self, row: dict, pdf_url: str) -> str:
        source_field = self.settings.supabase_source_name_field
        source_name = str(row.get(source_field) or "").strip()
        if source_name:
            return source_name

        asunto = str(row.get("asunto") or "").strip()
        if asunto:
            return asunto

        parsed = urlparse(pdf_url)
        filename = Path(parsed.path).name
        return filename or "documento_supabase"

    def _fetch_records(self) -> list[dict]:
        if not self.settings.supabase_url or not self.settings.supabase_service_role_key:
            raise ValueError(
                "Faltan credenciales de Supabase. Configura SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY."
            )

        records: list[dict] = []
        page_size = max(1, min(1000, self.settings.supabase_page_size))
        timeout = max(10, self.settings.supabase_request_timeout_seconds)
        offset = 0
        headers = {
            "apikey": self.settings.supabase_service_role_key,
            "Authorization": f"Bearer {self.settings.supabase_service_role_key}",
            "Accept": "application/json",
        }
        base_url = self.settings.supabase_url.rstrip("/")
        table = self.settings.supabase_table

        while True:
            response = requests.get(
                f"{base_url}/rest/v1/{table}",
                headers=headers,
                params={
                    "select": "*",
                    self.settings.supabase_pdf_url_field: "not.is.null",
                    "limit": page_size,
                    "offset": offset,
                },
                timeout=timeout,
            )
            response.raise_for_status()
            page = response.json()
            if not page:
                break
            if not isinstance(page, list):
                raise ValueError("Respuesta invalida de Supabase al listar documentos")

            records.extend(page)
            if len(page) < page_size:
                break
            offset += page_size

        return records

    def _extract_chunks_from_pdf_bytes(
        self,
        pdf_bytes: bytes,
        source_key: str,
        source_name: str,
        source_path: str,
    ) -> list[DocumentChunk]:
        chunks: list[DocumentChunk] = []
        ocr_unavailable = False
        document = fitz.open(stream=pdf_bytes, filetype="pdf")

        if self.settings.ocr_tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = self.settings.ocr_tesseract_cmd

        try:
            for page_index in range(len(document)):
                page = document[page_index]
                page_text = page.get_text("text").strip()
                if not page_text and self.settings.ocr_enabled and not ocr_unavailable:
                    try:
                        page_text = self._extract_page_text_with_ocr(page, self.settings.ocr_lang)
                    except pytesseract.TesseractNotFoundError:
                        ocr_unavailable = True
                        logger.warning(
                            "Tesseract OCR no disponible. Instala Tesseract o desactiva OCR_ENABLED para omitir OCR."
                        )
                    except Exception as exc:
                        logger.warning("Fallo OCR en %s p.%s: %s", source_name, page_index + 1, exc)

                if not page_text:
                    continue

                page_chunks = chunk_text(page_text, self.settings)
                for chunk_index, chunk in enumerate(page_chunks):
                    chunks.append(
                        DocumentChunk(
                            chunk_id=self._stable_chunk_id(source_key, page_index + 1, chunk_index, chunk),
                            text=chunk,
                            source_name=source_name,
                            source_path=source_path,
                            page_number=page_index + 1,
                            chunk_index=chunk_index,
                            metadata={
                                "page_label": f"p. {page_index + 1}",
                                "origin": "supabase",
                            },
                        )
                    )
        finally:
            document.close()

        return chunks

    def index_directory(
        self,
        progress_callback: Callable[[IngestionProgress], None] | None = None,
    ) -> IngestionSummary:
        summary = IngestionSummary()

        def _emit(
            *,
            stage: str,
            message: str,
            progress_percent: float,
            current_file: str | None = None,
            total_files: int = 0,
        ) -> None:
            if progress_callback is None:
                return
            progress_callback(
                IngestionProgress(
                    stage=stage,
                    message=message,
                    progress_percent=max(0.0, min(100.0, progress_percent)),
                    current_file=current_file,
                    total_files=total_files,
                    files_processed=summary.files_processed,
                    chunks_indexed=summary.chunks_indexed,
                )
            )

        try:
            records = self._fetch_records()
        except Exception as exc:
            summary.errors.append(str(exc))
            _emit(stage="error", message=f"Error consultando Supabase: {exc}", progress_percent=100)
            return summary

        filtered: list[tuple[str, dict]] = []
        url_field = self.settings.supabase_pdf_url_field
        for row in records:
            url = str(row.get(url_field) or "").strip()
            if url:
                filtered.append((url, row))

        if not filtered:
            msg = "No se encontraron registros con URL PDF en Supabase."
            summary.errors.append(msg)
            _emit(stage="empty", message=msg, progress_percent=100)
            return summary

        total_files = len(filtered)
        timeout = max(10, self.settings.supabase_request_timeout_seconds)
        _emit(
            stage="start",
            message=f"Preparando indexacion de {total_files} PDF(s) desde Supabase",
            progress_percent=1,
            total_files=total_files,
        )

        for index, (pdf_url, row) in enumerate(filtered, start=1):
            base = ((index - 1) / total_files) * 100
            source_name = self._build_source_name(row, pdf_url)
            source_key = str(row.get("id") or pdf_url)
            current_label = f"{source_name} ({index}/{total_files})"

            try:
                _emit(
                    stage="download",
                    message=f"Descargando PDF desde Supabase: {current_label}",
                    progress_percent=base + (0.20 * (100 / total_files)),
                    current_file=source_name,
                    total_files=total_files,
                )
                response = requests.get(pdf_url, timeout=timeout)
                response.raise_for_status()

                _emit(
                    stage="extracting",
                    message=f"Extrayendo texto: {current_label}",
                    progress_percent=base + (0.55 * (100 / total_files)),
                    current_file=source_name,
                    total_files=total_files,
                )
                chunks = self._extract_chunks_from_pdf_bytes(
                    pdf_bytes=response.content,
                    source_key=source_key,
                    source_name=source_name,
                    source_path=pdf_url,
                )

                if not chunks:
                    warning = f"{source_name}: no se extrajo texto del PDF"
                    summary.errors.append(warning)
                    _emit(
                        stage="file_warning",
                        message=warning,
                        progress_percent=(index / total_files) * 100,
                        current_file=source_name,
                        total_files=total_files,
                    )
                    continue

                _emit(
                    stage="indexing",
                    message=f"Guardando {len(chunks)} chunk(s) en Chroma: {current_label}",
                    progress_percent=base + (0.85 * (100 / total_files)),
                    current_file=source_name,
                    total_files=total_files,
                )
                indexed = self.knowledge_base.upsert_chunks(chunks)
                summary.files_processed += 1
                summary.chunks_indexed += indexed
                _emit(
                    stage="file_done",
                    message=f"Completado: {current_label}",
                    progress_percent=(index / total_files) * 100,
                    current_file=source_name,
                    total_files=total_files,
                )
            except Exception as exc:
                logger.exception("Error indexando PDF de Supabase %s", source_name)
                summary.errors.append(f"{source_name}: {exc}")
                _emit(
                    stage="file_error",
                    message=f"Error en {current_label}: {exc}",
                    progress_percent=(index / total_files) * 100,
                    current_file=source_name,
                    total_files=total_files,
                )

        _emit(stage="done", message="Indexacion finalizada", progress_percent=100, total_files=total_files)
        return summary

    def buscar(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        return self.knowledge_base.query(query, top_k=top_k)
