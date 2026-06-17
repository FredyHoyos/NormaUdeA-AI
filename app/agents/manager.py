from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

from app.agents.classifier import IntentClassifierAgent
from app.agents.retriever_agent import RetrieverAgent
from app.agents.writer_agent import WriterAgent
from app.config.settings import Settings
from app.domain.local_pdf_source import LocalPDFSource
from app.llm.client import LLMClient
from app.models import AnswerPayload, IngestionProgress, IngestionSummary
from app.retrieval.retriever import Retriever
from app.vectorstore.chroma_store import ChromaKnowledgeBase

try:
    from crewai import LLM as CrewLLM  # noqa: F401  reserved for future use
except Exception:
    CrewLLM = None

logger = logging.getLogger(__name__)


class CrewAIManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.llm_client = LLMClient(self.settings)
        self.knowledge_base = ChromaKnowledgeBase(self.settings)
        self.document_source = LocalPDFSource(self.settings, self.knowledge_base)
        self.retriever = Retriever(self.document_source, self.settings)
        self.classifier_agent = IntentClassifierAgent(self.settings, self.llm_client)
        self.retriever_agent = RetrieverAgent(self.settings, self.retriever)
        self.writer_agent = WriterAgent(self.settings, self.llm_client)

    def index_local_pdfs(
        self,
        pdf_dir: Path | None = None,
        progress_callback: Callable[[IngestionProgress], None] | None = None,
    ) -> IngestionSummary:
        return self.document_source.index_directory(pdf_dir, progress_callback=progress_callback)

    def answer(self, question: str) -> AnswerPayload:
        intent = self.classifier_agent.classify(question)
        hits = self.retriever_agent.recover(question) if intent.needs_retrieval else []
        context = self.retriever.build_context(hits)
        answer = self.writer_agent.draft_answer(question, intent, context, hits)
        answer.confidence = self._final_confidence(answer, hits, intent)
        return answer

    def _final_confidence(self, answer: AnswerPayload, hits: list, intent) -> float:
        if not hits:
            return min(0.35, answer.confidence or 0.2)
        top_score = max((hit.score for hit in hits), default=0.0)
        coverage = min(1.0, len({hit.source_name for hit in hits}) / 3.0)
        intent_score = float(getattr(intent, "confidence", 0.0) or 0.0)
        combined = (0.55 * top_score) + (0.25 * coverage) + (0.20 * intent_score)
        return round(max(answer.confidence, combined), 3)
