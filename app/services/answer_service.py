from __future__ import annotations

from app.agents.manager import CrewAIManager
from app.models import AnswerPayload, IngestionSummary


class AnswerService:
    def __init__(self, manager: CrewAIManager) -> None:
        self.manager = manager

    def index_documents(self) -> IngestionSummary:
        return self.manager.index_local_pdfs()

    def answer(self, question: str) -> AnswerPayload:
        return self.manager.answer(question)
