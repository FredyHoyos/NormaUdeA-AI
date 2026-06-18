"""Servicio de respuesta — wrappea el manager de CrewAI con logging analítico."""

from __future__ import annotations

import time
from collections.abc import Callable

from app.agents.manager import CrewAIManager
from app.analytics.interaction_logger import InteractionLogger
from app.config.settings import get_settings
from app.models import AnswerPayload, IngestionProgress, IngestionSummary


class AnswerService:
    def __init__(self, manager: CrewAIManager) -> None:
        self.manager = manager
        settings = get_settings()
        self.logger = InteractionLogger(settings.analytics_db_path)
        self._model_provider = settings.llm_provider

    def index_documents(self, progress_callback: Callable[[IngestionProgress], None] | None = None) -> IngestionSummary:
        return self.manager.index_local_pdfs(progress_callback=progress_callback)

    def answer(self, question: str, chat_history: list[dict[str, str]] | None = None) -> AnswerPayload:
        t0 = time.perf_counter()
        answer = self.manager.answer(question, chat_history=chat_history)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        # Enriquecer el payload con el tiempo de procesamiento
        answer.processing_time_ms = round(elapsed_ms, 2)

        # Registrar en SQLite
        self.logger.log_interaction(
            question=question,
            intent_category=answer.intent.category,
            confidence=answer.confidence,
            processing_time_ms=elapsed_ms,
            documents_used_count=len(answer.documents_used),
            model_provider=self._model_provider,
            notes="; ".join(answer.notes[:3]),
        )

        return answer
