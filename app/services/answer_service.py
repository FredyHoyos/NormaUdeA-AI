from __future__ import annotations

from collections.abc import Callable

from app.agents.manager import CrewAIManager
from app.models import AnswerPayload, IngestionProgress, IngestionSummary


class AnswerService:
    def __init__(self, manager: CrewAIManager) -> None:
        self.manager = manager

    def index_documents(self, progress_callback: Callable[[IngestionProgress], None] | None = None) -> IngestionSummary:
        return self.manager.index_local_pdfs(progress_callback=progress_callback)

    def answer(self, question: str) -> AnswerPayload:
        return self.manager.answer(question)
