from __future__ import annotations

import hashlib
import json
import logging
import re
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path

import requests
from supabase import Client, create_client

from app.config.settings import Settings
from app.domain.document_source import DocumentSource
from app.ingestion.chunking import chunk_text
from app.ingestion.pdf_loader import extract_pdf_chunks_from_bytes, is_ocr_runtime_available
from app.models import DocumentChunk, IngestionProgress, IngestionSummary, RetrievalHit
from app.vectorstore.chroma_store import ChromaKnowledgeBase

logger = logging.getLogger(__name__)


class SupabasePDFSource(DocumentSource):
    def __init__(self, settings: Settings, knowledge_base: ChromaKnowledgeBase) -> None:
        self.settings = settings
        self.knowledge_base = knowledge_base
        self._client = self._build_client()

    def _build_client(self) -> Client:
        if not self.settings.supabase_url or not self.settings.supabase_service_role_key:
            raise ValueError("SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY son obligatorios para usar SupabasePDFSource")
        return create_client(self.settings.supabase_url, self.settings.supabase_service_role_key)

    @staticmethod
    def _safe_name(value: str) -> str:
        clean = re.sub(r"[^A-Za-z0-9_-]+", "_", value).strip("_")
        return clean or "documento"

    def _state_file(self) -> Path:
        return self.settings.supabase_index_state_path

    def _load_state(self) -> dict:
        state_file = self._state_file()
        if not state_file.exists():
            return {"version": 1, "documents": {}}
        try:
            payload = json.loads(state_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                return {"version": 1, "documents": {}}
            docs = payload.get("documents")
            if not isinstance(docs, dict):
                payload["documents"] = {}
            return payload
        except Exception:
            logger.warning("No se pudo leer estado de indexacion incremental. Se recreara.")
            return {"version": 1, "documents": {}}

    def _save_state(self, state: dict) -> None:
        state_file = self._state_file()
        state_file.parent.mkdir(parents=True, exist_ok=True)
        state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _record_key(row: dict, pdf_url: str) -> str:
        identifier = str(row.get("id") or "").strip()
        return identifier or pdf_url

    @staticmethod
    def _record_signature(row: dict, pdf_url: str) -> str:
        resuelve = str(row.get("resuelve") or "").strip()
        raw = "|".join(
            [
                str(row.get("id") or ""),
                str(row.get("fecha_expedicion") or ""),
                str(row.get("fecha_rastreo") or ""),
                str(row.get("numero") or ""),
                str(row.get("asunto") or ""),
                str(row.get("tipo_documento") or ""),
                str(pdf_url or ""),
                resuelve[:500],
            ]
        )
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    @staticmethod
    def _truncate_text(value: str, limit: int = 800) -> str:
        text = " ".join(str(value).split()).strip()
        return text[:limit]

    def _build_resuelve_fallback_chunks(
        self,
        *,
        row: dict,
        source_name: str,
        source_path: str,
    ) -> list[DocumentChunk]:
        if not self.settings.supabase_use_resuelve_fallback:
            return []

        resuelve = str(row.get("resuelve") or "").strip()
        if not resuelve:
            return []

        text = self._truncate_text(resuelve, limit=self.settings.supabase_resuelve_max_chars)
        preface = (
            "Resumen catalogado del documento (campo resuelve de base de datos). "
            "Usar como apoyo cuando el PDF no contiene texto extraible: "
        )
        fallback_text = f"{preface}{text}"
        chunks_text = chunk_text(fallback_text, self.settings)
        chunks: list[DocumentChunk] = []

        for idx, chunk in enumerate(chunks_text):
            chunk_id = hashlib.sha1(f"{source_path}:resuelve:{idx}:{chunk}".encode("utf-8")).hexdigest()[:24]
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    text=chunk,
                    source_name=source_name,
                    source_path=source_path,
                    page_number=None,
                    chunk_index=idx,
                    metadata={
                        "origin": "supabase_resuelve_fallback",
                        "page_label": "sin_pagina",
                    },
                )
            )
        return chunks

    def _build_source_name(self, row: dict, fallback_index: int) -> str:
        numero = str(row.get("numero") or "").strip()
        asunto = str(row.get("asunto") or "").strip()
        tipo_documento = str(row.get("tipo_documento") or "").strip()

        if numero and asunto:
            return self._safe_name(f"{numero}_{asunto[:70]}")
        if numero and tipo_documento:
            return self._safe_name(f"{numero}_{tipo_documento}")
        if numero:
            return self._safe_name(numero)
        if asunto:
            return self._safe_name(asunto[:80])
        if tipo_documento:
            return self._safe_name(tipo_documento)
        return self._safe_name(f"documento_{fallback_index}")

    def _build_row_metadata(self, row: dict) -> dict:
        metadata: dict[str, str] = {
            "origin": "supabase",
        }

        for key in ("id", "numero", "tipo_documento", "asunto", "fecha_expedicion", "fecha_rastreo"):
            value = row.get(key)
            if value is not None and str(value).strip():
                metadata[f"db_{key}"] = str(value).strip()

        resuelve = str(row.get("resuelve") or "").strip()
        if resuelve:
            metadata["db_resuelve"] = self._truncate_text(resuelve, limit=1000)

        return metadata

    def _fetch_records(self) -> list[dict]:
        response = (
            self._client.table(self.settings.supabase_table_name)
            .select(self.settings.supabase_select_columns)
            .execute()
        )
        data = response.data or []
        return [row for row in data if isinstance(row, dict)]

    def _download_pdf(self, url: str) -> bytes:
        response = requests.get(url, timeout=self.settings.supabase_pdf_timeout_seconds)
        response.raise_for_status()
        return response.content

    def index_directory(
        self,
        pdf_dir: Path | None = None,
        progress_callback: Callable[[IngestionProgress], None] | None = None,
    ) -> IngestionSummary:
        summary = IngestionSummary()
        state = self._load_state()
        state_docs: dict = state.setdefault("documents", {})
        ocr_available = is_ocr_runtime_available(self.settings)

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
            summary.errors.append(f"No se pudo leer la tabla de Supabase: {exc}")
            _emit(
                stage="error",
                message=f"No se pudo leer la tabla de Supabase: {exc}",
                progress_percent=100,
            )
            return summary

        valid_records = [
            row for row in records if str(row.get(self.settings.supabase_pdf_url_column, "")).strip()
        ]

        if not valid_records:
            summary.errors.append(
                f"No se encontraron registros con la columna '{self.settings.supabase_pdf_url_column}' en {self.settings.supabase_table_name}"
            )
            _emit(
                stage="empty",
                message="No se encontraron documentos PDF en Supabase.",
                progress_percent=100,
            )
            return summary

        total_files = len(valid_records)
        _emit(
            stage="start",
            message=(
                f"Preparando indexacion de {total_files} PDF(s) desde Supabase "
                f"(OCR {'disponible' if ocr_available else 'no disponible'})"
            ),
            progress_percent=1,
            total_files=total_files,
        )

        for index, row in enumerate(valid_records, start=1):
            base = ((index - 1) / total_files) * 100
            url = str(row.get(self.settings.supabase_pdf_url_column, "")).strip()
            source_name = self._build_source_name(row, fallback_index=index)
            row_metadata = self._build_row_metadata(row)
            record_key = self._record_key(row, url)
            signature = self._record_signature(row, url)
            previous = state_docs.get(record_key) if isinstance(state_docs, dict) else None
            previous_chunks = int(previous.get("chunks_indexed", 0)) if isinstance(previous, dict) else 0
            previous_ocr = bool(previous.get("ocr_available", False)) if isinstance(previous, dict) else False
            unchanged = isinstance(previous, dict) and previous.get("signature") == signature
            needs_retry_after_ocr = unchanged and previous_chunks == 0 and ocr_available and not previous_ocr

            if unchanged and not needs_retry_after_ocr:
                summary.reused_files += 1
                _emit(
                    stage="skipped",
                    message=f"Sin cambios, se reutiliza indexacion previa: {source_name}",
                    progress_percent=(index / total_files) * 100,
                    current_file=source_name,
                    total_files=total_files,
                )
                continue

            try:
                _emit(
                    stage="extracting",
                    message=f"Descargando PDF {index}/{total_files}: {source_name}",
                    progress_percent=base + (0.3 * (100 / total_files)),
                    current_file=source_name,
                    total_files=total_files,
                )

                pdf_bytes = self._download_pdf(url)
                chunks = extract_pdf_chunks_from_bytes(
                    pdf_content=pdf_bytes,
                    source_name=source_name,
                    source_path=url,
                    settings=self.settings,
                )

                used_fallback = False
                if not chunks:
                    chunks = self._build_resuelve_fallback_chunks(
                        row=row,
                        source_name=source_name,
                        source_path=url,
                    )
                    if chunks:
                        used_fallback = True
                        summary.fallback_files += 1

                if chunks:
                    chunks = [
                        chunk.model_copy(update={"metadata": {**chunk.metadata, **row_metadata}})
                        for chunk in chunks
                    ]

                if not chunks:
                    warning = f"{source_name}: no se extrajo texto del PDF remoto."
                    summary.errors.append(warning)
                    state_docs[record_key] = {
                        "signature": signature,
                        "chunks_indexed": 0,
                        "ocr_available": ocr_available,
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
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
                    message=f"Guardando {len(chunks)} chunk(s) en Chroma para {source_name}",
                    progress_percent=base + (0.75 * (100 / total_files)),
                    current_file=source_name,
                    total_files=total_files,
                )

                indexed = self.knowledge_base.upsert_chunks(chunks)
                summary.files_processed += 1
                summary.chunks_indexed += indexed
                state_docs[record_key] = {
                    "signature": signature,
                    "chunks_indexed": indexed,
                    "ocr_available": ocr_available,
                    "used_fallback": used_fallback,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }

                _emit(
                    stage="file_done",
                    message=f"Completado {source_name} ({index}/{total_files})",
                    progress_percent=(index / total_files) * 100,
                    current_file=source_name,
                    total_files=total_files,
                )
            except Exception as exc:
                logger.exception("Error indexando PDF remoto %s", source_name)
                summary.errors.append(f"{source_name}: {exc}")
                state_docs[record_key] = {
                    "signature": signature,
                    "chunks_indexed": 0,
                    "ocr_available": ocr_available,
                    "error": str(exc),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }
                _emit(
                    stage="file_error",
                    message=f"Error en {source_name}: {exc}",
                    progress_percent=(index / total_files) * 100,
                    current_file=source_name,
                    total_files=total_files,
                )

        _emit(
            stage="done",
            message="Indexacion finalizada",
            progress_percent=100,
            total_files=total_files,
        )
        try:
            self._save_state(state)
        except Exception as exc:
            logger.warning("No se pudo guardar el estado incremental de indexacion: %s", exc)

        return summary

    def buscar(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        return self.knowledge_base.query(query, top_k=top_k)
