from __future__ import annotations

import logging

from crewai import Agent

from app.agents.tools import DocumentSearchTool
from app.config.settings import Settings
from app.models import RetrievalHit
from app.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)


class RetrieverAgent:
    def __init__(self, settings: Settings, retriever: Retriever, crew_llm=None) -> None:
        self.settings = settings
        self.retriever = retriever
        self.crewai_agent = self._build_crewai_agent(crew_llm)

    def _build_crewai_agent(self, crew_llm):
        llm = crew_llm
        if llm is None:
            return None
        search_tool = DocumentSearchTool(retriever=self.retriever)
        return Agent(
            role="Recuperador de Documentos",
            goal="Buscar y recuperar fragmentos de documentos normativos y academicos relevantes para la consulta del usuario",
            backstory="Especialista en busqueda documental dentro del repositorio de normativas, reglamentos y procedimientos academicos de la Universidad de Antioquia.",
            llm=llm,
            tools=[search_tool],
            verbose=False,
        )

    def recover(self, question: str) -> list[RetrievalHit]:
        return self.retriever.retrieve(question, top_k=self.settings.retrieval_k)
