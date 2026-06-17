from __future__ import annotations

import logging

from app.config.settings import Settings
from app.llm.client import LLMClient
from app.models import AnswerPayload, QuestionIntent, RetrievalHit

try:  # pragma: no cover - optional during bootstrap
    from crewai import Agent
except Exception:  # pragma: no cover
    Agent = None

logger = logging.getLogger(__name__)


class WriterAgent:
    def __init__(self, settings: Settings, llm_client: LLMClient, crew_llm=None) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.crewai_agent = self._build_crewai_agent(crew_llm)

    def _build_crewai_agent(self, crew_llm=None):
        # Los agentes CrewAI se reservan para una etapa posterior con Tasks/Crew.
        # La redaccion actual usa directamente LLMClient.
        return None

    def draft_answer(
        self,
        question: str,
        intent: QuestionIntent,
        context: str,
        hits: list[RetrievalHit],
    ) -> AnswerPayload:
        system_prompt = (
            "Eres un redactor experto en respuestas administrativas universitarias. "
            "Responde en espanol, usa solo la evidencia entregada, no inventes informacion y devuelve solo JSON valido."
        )
        sources_summary = "\n".join(
            f"[{index}] {hit.source_name} | p. {hit.page_number or 'N/A'} | score={hit.score:.3f}"
            for index, hit in enumerate(hits, start=1)
        )
        prompt = f"""
Pregunta:
{question}

Intencion:
{intent.model_dump_json(indent=2)}

Contexto recuperado:
{context}

Fuentes disponibles:
{sources_summary}

Devuelve un JSON con estas llaves:
- answer: respuesta final en espanol, concisa pero fundamentada
- confidence: numero entre 0 y 1
- documents_used: lista de nombres de documentos
- notes: lista breve de observaciones o limites

Instrucciones:
- Si la evidencia no alcanza, dilo explicitamente.
- Usa referencias internas como [1], [2] cuando sea pertinente.
- No agregues llaves adicionales.
"""
        try:
            payload = self.llm_client.complete_json(prompt=prompt, system_prompt=system_prompt)
            documents_used = payload.get("documents_used") or [hit.source_name for hit in hits]
            notes = payload.get("notes") or []
            return AnswerPayload(
                answer=str(payload.get("answer", "No se pudo redactar una respuesta.")),
                intent=intent,
                confidence=float(payload.get("confidence", 0.0) or 0.0),
                documents_used=[str(document) for document in documents_used],
                sources=hits,
                notes=[str(note) for note in notes],
            )
        except Exception as exc:  # pragma: no cover - defensive fallback
            logger.exception("Fallo el agente redactor")
            return AnswerPayload(
                answer=f"No fue posible redactar la respuesta con el LLM configurado. Detalle: {exc}",
                intent=intent,
                confidence=0.0,
                documents_used=[hit.source_name for hit in hits],
                sources=hits,
                notes=["Se uso respuesta de contingencia por error en el proveedor LLM."],
            )
