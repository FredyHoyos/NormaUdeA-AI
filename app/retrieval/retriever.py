from __future__ import annotations

import logging

from app.config.settings import Settings
from app.domain.document_source import DocumentSource
from app.llm.client import LLMClient
from app.models import RetrievalHit
from app.retrieval.re_ranker import ReRanker

logger = logging.getLogger(__name__)


class Retriever:
    def __init__(self, document_source: DocumentSource, settings: Settings, llm_client: LLMClient | None = None) -> None:
        self.document_source = document_source
        self.settings = settings
        self.reranker = ReRanker(settings, llm_client) if settings.reranker_enabled else None

    def retrieve(self, query: str, top_k: int | None = None) -> list[RetrievalHit]:
        initial_k = top_k or self.settings.retrieval_k
        if self.reranker is not None:
            initial_k = max(initial_k, self.settings.reranker_retrieval_k)
        hits = self.document_source.buscar(query=query, top_k=initial_k)
        if self.reranker is not None and len(hits) > 1:
            hits = self.reranker.rerank(query, hits)
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
