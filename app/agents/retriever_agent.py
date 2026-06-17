from __future__ import annotations

import logging

from app.config.settings import Settings
from app.retrieval.retriever import Retriever

try:  # pragma: no cover - optional during bootstrap
    from crewai import Agent
except Exception:  # pragma: no cover
    Agent = None

logger = logging.getLogger(__name__)


class RetrieverAgent:
    def __init__(self, settings: Settings, retriever: Retriever, crew_llm=None) -> None:
        self.settings = settings
        self.retriever = retriever
        self.crewai_agent = self._build_crewai_agent(crew_llm)

    def _build_crewai_agent(self, crew_llm=None):
        # Los agentes CrewAI se reservan para una etapa posterior con Tasks/Crew.
        # La recuperacion actual usa directamente el Retriever.
        return None

    def recover(self, question: str) -> list:
        return self.retriever.retrieve(question, top_k=self.settings.retrieval_k)
