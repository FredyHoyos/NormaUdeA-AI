from __future__ import annotations

import logging
from pathlib import Path

from app.config.settings import Settings
from app.domain.document_source import DocumentSource
from app.ingestion.pdf_loader import extract_pdf_chunks
from app.models import IngestionSummary, RetrievalHit
from app.vectorstore.chroma_store import ChromaKnowledgeBase

logger = logging.getLogger(__name__)


class LocalPDFSource(DocumentSource):
    def __init__(self, settings: Settings, knowledge_base: ChromaKnowledgeBase) -> None:
        self.settings = settings
        self.knowledge_base = knowledge_base

    def index_directory(self, pdf_dir: Path | None = None) -> IngestionSummary:
        folder = pdf_dir or self.settings.pdf_dir
        summary = IngestionSummary()

        if not folder.exists():
            summary.errors.append(f"La carpeta de PDFs no existe: {folder}")
            return summary

        pdf_files = sorted(folder.glob("**/*.pdf"))
        if not pdf_files:
            summary.errors.append(f"No se encontraron PDFs en: {folder}")
            return summary

        for pdf_file in pdf_files:
            try:
                chunks = extract_pdf_chunks(pdf_file, self.settings)
                indexed = self.knowledge_base.upsert_chunks(chunks)
                summary.files_processed += 1
                summary.chunks_indexed += indexed
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.exception("Error indexando %s", pdf_file)
                summary.errors.append(f"{pdf_file.name}: {exc}")

        return summary

    def buscar(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        return self.knowledge_base.query(query, top_k=top_k)
