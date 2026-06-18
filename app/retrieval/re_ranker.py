from __future__ import annotations

import logging
from typing import Any

from app.config.settings import Settings
from app.llm.client import LLMClient
from app.models import RetrievalHit

logger = logging.getLogger(__name__)

_RERANK_PROMPT = """Eres un re-ranker de documentos. Dada una consulta y una lista de fragmentos, ordinalos por relevancia.

Consulta: {query}

Fragmentos:
{fragments}

Devuelve un JSON con una lista "rankings" donde cada elemento tiene:
- index: numero del fragmento (1-based)
- relevance: puntuacion de relevancia entre 0.0 y 1.0
- reason: breve razon (max 20 palabras)

Ordena los fragmentos del mas relevante al menos relevante.
"""


class ReRanker:
    def __init__(self, settings: Settings, llm_client: LLMClient | None = None) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self._model: Any = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from sentence_transformers import CrossEncoder

            device = "cpu"
            logger.info("Cargando cross-encoder %s en %s", self.settings.reranker_model, device)
            self._model = CrossEncoder(self.settings.reranker_model, device=device)
        except Exception as exc:
            logger.warning("No se pudo cargar cross-encoder (%s). Usando fallback LLM.", exc)
            self._model = None
        return self._model

    def rerank(self, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        if not hits or len(hits) <= 1:
            return hits

        ce_model = self._load_model()
        if ce_model is not None:
            return self._model_rerank(query, hits, ce_model)

        if self.settings.reranker_use_llm_fallback and self.llm_client is not None:
            return self._llm_rerank(query, hits)

        logger.info("Re-ranker no disponible, devolviendo hits sin reordenar")
        return hits

    def _model_rerank(self, query: str, hits: list[RetrievalHit], model: Any) -> list[RetrievalHit]:
        pairs = [(query, hit.text) for hit in hits]
        try:
            scores = model.predict(pairs, show_progress_bar=False)
        except Exception as exc:
            logger.warning("Fallo cross-encoder predict (%s). Usando LLM fallback.", exc)
            if self.settings.reranker_use_llm_fallback and self.llm_client is not None:
                return self._llm_rerank(query, hits)
            return hits

        ranked = list(zip(hits, scores))
        ranked.sort(key=lambda x: float(x[1]), reverse=True)

        reranked: list[RetrievalHit] = []
        for hit, score in ranked:
            reranked.append(hit.model_copy(update={"score": round(max(0.0, min(1.0, float(score))), 4)}))
        final_k = max(1, self.settings.reranker_final_k)
        result = reranked[:final_k]
        logger.info("Re-rank: %s -> %s hits (cross-encoder)", len(hits), len(result))
        return result

    def _llm_rerank(self, query: str, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        fragments = "\n\n".join(
            f"[{i}] {h.text[:200]}"
            for i, h in enumerate(hits, start=1)
        )
        prompt = _RERANK_PROMPT.format(query=query, fragments=fragments)
        try:
            payload = self.llm_client.complete_json(prompt=prompt)
            rankings = payload.get("rankings", [])
        except Exception as exc:
            logger.warning("Fallo LLM re-rank (%s). Devolviendo hits sin reordenar.", exc)
            return hits

        if not rankings:
            return hits

        index_map = {i: h for i, h in enumerate(hits, start=1)}
        ordered: list[tuple[int, RetrievalHit, float]] = []
        for entry in rankings:
            idx = int(entry.get("index", 0))
            relevance = float(entry.get("relevance", 0.0))
            if idx in index_map:
                ordered.append((idx, index_map[idx], relevance))

        ordered.sort(key=lambda x: x[2], reverse=True)
        reranked = [h.model_copy(update={"score": s}) for _, h, s in ordered]
        result = reranked[:max(1, self.settings.reranker_final_k)]
        logger.info("Re-rank: %s -> %s hits (LLM)", len(hits), len(result))
        return result
