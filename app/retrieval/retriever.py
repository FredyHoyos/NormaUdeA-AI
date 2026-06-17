from __future__ import annotations

import logging

from app.config.settings import Settings
from app.domain.document_source import DocumentSource
from app.models import RetrievalHit

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self, document_source: DocumentSource, settings: Settings) -> None:
        self.document_source = document_source
        self.settings = settings

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievalHit]:
        limit = top_k or self.settings.retrieval_k
        hits = self.document_source.buscar(query=query, top_k=limit)
        logger.info("Recuperados %s fragmentos para la consulta", len(hits))
        return hits

    def build_context(self, hits: list[RetrievalHit]) -> str:
        if not hits:
            return "No se recupero evidencia documental relevante."

        blocks: list[str] = []
        for index, hit in enumerate(hits, start=1):
            page_text = f"p. {hit.page_number}" if hit.page_number else "pagina no identificada"
            blocks.append(
                f"[{index}] Fuente: {hit.source_name} | {page_text} | score={hit.score:.3f}\n{hit.text.strip()}"
            )
        context = "\n\n".join(blocks)
        return context[: self.settings.max_context_chars]
