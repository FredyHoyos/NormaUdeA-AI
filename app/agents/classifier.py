from __future__ import annotations

import logging

from app.config.settings import Settings
from app.llm.client import LLMClient
from app.models import QuestionIntent

try:  # pragma: no cover - dependency optional during bootstrap
    from crewai import Agent
except Exception:  # pragma: no cover - fallback when CrewAI is unavailable
    Agent = None

logger = logging.getLogger(__name__)


class IntentClassifierAgent:
    def __init__(self, settings: Settings, llm_client: LLMClient, crew_llm=None) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.crewai_agent = self._build_crewai_agent(crew_llm)

    def _build_crewai_agent(self, crew_llm=None):
        # Los agentes CrewAI se reservan para una etapa posterior con Tasks/Crew.
        # La clasificacion actual usa directamente LLMClient.
        return None

    def classify(self, question: str) -> QuestionIntent:
        system_prompt = (
            "Eres el clasificador de un copiloto administrativo universitario. "
            "Devuelve solo JSON valido con las llaves category, needs_retrieval, confidence y rationale."
        )
        prompt = f"""
Clasifica la siguiente consulta.

Consulta:
{question}

Categorias sugeridas: academic, administrative, regulation, procedures, general, other.

Reglas:
- needs_retrieval debe ser true si la respuesta depende de documentos.
- confidence debe ser un numero entre 0 y 1.
- rationale debe ser breve y concreta.
"""
        try:
            payload = self.llm_client.complete_json(prompt=prompt, system_prompt=system_prompt)
            return QuestionIntent(
                category=str(payload.get("category", "general")),
                needs_retrieval=bool(payload.get("needs_retrieval", True)),
                confidence=float(payload.get("confidence", 0.0) or 0.0),
                rationale=str(payload.get("rationale", "") or ""),
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("Fallo la clasificacion de intencion")
            return QuestionIntent(category="general", needs_retrieval=True, confidence=0.2, rationale=str(exc))
