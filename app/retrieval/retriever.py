from __future__ import annotations

import logging
import re
import unicodedata

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
        hits = self._prioritize_article_hits(query, hits)
        if self.reranker is not None and len(hits) > 1:
            hits = self.reranker.rerank(query, hits)
        logger.info("Recuperados %s fragmentos para la consulta", len(hits))
        return hits

    @staticmethod
    def _normalize(text: str) -> str:
        # Normaliza acentos y mayusculas para comparar "artículo" y "articulo" sin friccion.
        normalized = unicodedata.normalize("NFD", text or "")
        normalized = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
        return normalized.lower()

    @classmethod
    def _extract_article_number(cls, query: str) -> int | None:
        normalized = cls._normalize(query)
        match = re.search(r"\barticulo\s+(\d{1,4})\b", normalized)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    @classmethod
    def _is_pregrado_query(cls, query: str) -> bool:
        normalized = cls._normalize(query)
        return "pregrado" in normalized

    @classmethod
    def _is_pregrado_hit(cls, hit: RetrievalHit) -> bool:
        source = cls._normalize(hit.source_name)
        if "pregrado" in source:
            return True
        metadata = hit.metadata or {}
        for key in ("db_asunto", "db_tipo_documento"):
            value = cls._normalize(str(metadata.get(key) or ""))
            if "pregrado" in value:
                return True
        return False

    @classmethod
    def _has_exact_article(cls, hit: RetrievalHit, article_number: int) -> bool:
        text = cls._normalize(hit.text)
        # Evita falsos positivos como "178" cuando se consulta "78".
        pattern = rf"\barticulo\s+{article_number}\b"
        return re.search(pattern, text) is not None

    @classmethod
    def _prioritize_article_hits(cls, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        article_number = cls._extract_article_number(query)
        if article_number is None or not hits:
            return hits

        pregrado_query = cls._is_pregrado_query(query)
        exact_hits: list[RetrievalHit] = []
        non_exact_hits: list[RetrievalHit] = []

        for hit in hits:
            if cls._has_exact_article(hit, article_number):
                exact_hits.append(hit)
            else:
                non_exact_hits.append(hit)

        if exact_hits:
            if pregrado_query:
                exact_hits.sort(key=lambda h: (not cls._is_pregrado_hit(h), -h.score))
                non_exact_hits.sort(key=lambda h: (not cls._is_pregrado_hit(h), -h.score))
            else:
                exact_hits.sort(key=lambda h: -h.score)
                non_exact_hits.sort(key=lambda h: -h.score)
            return [*exact_hits, *non_exact_hits]

        # Si no hay match exacto del articulo en los primeros hits, prioriza por contexto de pregrado cuando aplique.
        if pregrado_query:
            return sorted(hits, key=lambda h: (not cls._is_pregrado_hit(h), -h.score))

        return hits

    def build_context(self, hits: list[RetrievalHit]) -> str:
        if not hits:
            return "No se recupero evidencia documental relevante."

        blocks: list[str] = []
        for index, hit in enumerate(hits, start=1):
            page_text = f"p. {hit.page_number}" if hit.page_number else "pagina no identificada"
            metadata_parts: list[str] = []
            metadata = hit.metadata or {}

            numero = str(metadata.get("db_numero") or "").strip()
            tipo = str(metadata.get("db_tipo_documento") or "").strip()
            asunto = str(metadata.get("db_asunto") or "").strip()
            fecha = str(metadata.get("db_fecha_expedicion") or "").strip()

            if numero:
                metadata_parts.append(f"numero={numero}")
            if tipo:
                metadata_parts.append(f"tipo={tipo}")
            if fecha:
                metadata_parts.append(f"fecha={fecha}")
            if asunto:
                metadata_parts.append(f"asunto={asunto[:120]}")

            metadata_line = f"\nMeta: {' | '.join(metadata_parts)}" if metadata_parts else ""
            blocks.append(
                f"[{index}] Fuente: {hit.source_name} | {page_text} | score={hit.score:.3f}{metadata_line}\n{hit.text.strip()}"
            )
        context = "\n\n".join(blocks)
        return context[: self.settings.max_context_chars]
