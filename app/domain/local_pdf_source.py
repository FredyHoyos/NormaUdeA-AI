from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from app.config.settings import Settings
from app.domain.document_source import DocumentSource
from app.ingestion.pdf_loader import extract_pdf_chunks
from app.models import IngestionProgress, IngestionSummary, RetrievalHit
from app.vectorstore.chroma_store import ChromaKnowledgeBase

logger = logging.getLogger(__name__)


class LocalPDFSource(DocumentSource):
    def __init__(self, settings: Settings, knowledge_base: ChromaKnowledgeBase) -> None:
        self.settings = settings
        self.knowledge_base = knowledge_base

    def index_directory(
        self,
        pdf_dir: Path | None = None,
        progress_callback: Callable[[IngestionProgress], None] | None = None,
    ) -> IngestionSummary:
        folder = pdf_dir or self.settings.pdf_dir
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

        if not folder.exists():
            summary.errors.append(f"La carpeta de PDFs no existe: {folder}")
            _emit(
                stage="error",
                message=f"La carpeta de PDFs no existe: {folder}",
                progress_percent=100,
            )
            return summary

        pdf_files = sorted(folder.glob("**/*.pdf"))
        if not pdf_files:
            summary.errors.append(f"No se encontraron PDFs en: {folder}")
            _emit(
                stage="empty",
                message=f"No se encontraron PDFs en: {folder}",
                progress_percent=100,
            )
            return summary

        total_files = len(pdf_files)
        _emit(
            stage="start",
            message=f"Preparando indexacion de {total_files} PDF(s)",
            progress_percent=1,
            total_files=total_files,
        )

        for index, pdf_file in enumerate(pdf_files, start=1):
            base = ((index - 1) / total_files) * 100
            try:
                _emit(
                    stage="extracting",
                    message=f"Extrayendo texto de {pdf_file.name} ({index}/{total_files})",
                    progress_percent=base + (0.25 * (100 / total_files)),
                    current_file=pdf_file.name,
                    total_files=total_files,
                )
                chunks = extract_pdf_chunks(pdf_file, self.settings)
                if not chunks:
                    warning = (
                        f"{pdf_file.name}: no se extrajo texto. "
                        "El PDF puede ser imagen/escaneado y requerir OCR."
                    )
                    summary.errors.append(warning)
                    _emit(
                        stage="file_warning",
                        message=warning,
                        progress_percent=(index / total_files) * 100,
                        current_file=pdf_file.name,
                        total_files=total_files,
                    )
                    continue

                _emit(
                    stage="indexing",
                    message=f"Guardando {len(chunks)} chunk(s) en Chroma para {pdf_file.name}",
                    progress_percent=base + (0.75 * (100 / total_files)),
                    current_file=pdf_file.name,
                    total_files=total_files,
                )
                indexed = self.knowledge_base.upsert_chunks(chunks)
                summary.files_processed += 1
                summary.chunks_indexed += indexed
                _emit(
                    stage="file_done",
                    message=f"Completado {pdf_file.name} ({index}/{total_files})",
                    progress_percent=(index / total_files) * 100,
                    current_file=pdf_file.name,
                    total_files=total_files,
                )
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Error indexando %s", pdf_file)
                summary.errors.append(f"{pdf_file.name}: {exc}")
                _emit(
                    stage="file_error",
                    message=f"Error en {pdf_file.name}: {exc}",
                    progress_percent=(index / total_files) * 100,
                    current_file=pdf_file.name,
                    total_files=total_files,
                )

        _emit(
            stage="done",
            message="Indexacion finalizada",
            progress_percent=100,
            total_files=total_files,
        )

        return summary

    def buscar(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        return self.knowledge_base.query(query, top_k=top_k)
