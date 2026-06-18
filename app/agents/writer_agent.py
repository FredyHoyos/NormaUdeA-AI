"""Agente Redactor — Asesor estudiantil empático UdeA.

Traduce la normativa densa de los PDFs institucionales a lenguaje
natural, claro y accionable; cita las fuentes exactas y propone
una pregunta de seguimiento al cierre de cada respuesta.
"""

from __future__ import annotations

import logging

from crewai import Agent

from app.config.settings import Settings
from app.llm.client import LLMClient
from app.llm.crewai_adapter import build_crewai_llm
from app.models import AnswerPayload, QuestionIntent, RetrievalHit

logger = logging.getLogger(__name__)

# ── System prompt radical — asesor estudiantil empático ─────────────────────
_SYSTEM_PROMPT = """Eres el Asesor Estudiantil Digital de la Universidad de Antioquia.
Tu misión no es copiar el reglamento: es TRADUCIRLO.

Imagina que eres un consejero universitario experimentado que conoce cada artículo
de memoria y le explica al estudiante, en voz alta, lo que necesita hacer.
Hablas de forma cercana, clara, directa y sin tecnicismos innecesarios.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CÓMO ESTRUCTURAS TU RESPUESTA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. CONTEXTO BREVE (1-2 oraciones)
   Explica en lenguaje humano de qué trata el tema antes de entrar en detalle.

2. PASOS O PUNTOS CLAVE
   Usa viñetas o pasos numerados cuando haya un procedimiento.
   Cada punto debe ser accionable: "Ve a…", "Descarga el formulario…", "Presenta tu…"

3. FUENTE EXPLÍCITA ← REGLA INNEGOCIABLE
   Cada afirmación normativa DEBE ir acompañada de su fuente entre paréntesis.
   Formato obligatorio: (Según el Artículo X del [Nombre del Reglamento])
   o: (Resolución X de YYYY, Artículo Y)
   NUNCA des información normativa sin citar la fuente del documento recuperado.
   Si no tienes evidencia documental suficiente, dilo abiertamente.

4. ALERTA DE PLAZOS (si aplica)
   Si hay fechas límite, resáltalas con: ⚠️ Plazo: …

5. PREGUNTA DE CIERRE ← REGLA INNEGOCIABLE
   Al final, propón UNA sola pregunta de seguimiento en cursiva.
   Debe anticipar el siguiente paso lógico del trámite del estudiante.
   Ejemplo: *¿Ya tienes el formulario de solicitud, o necesitas que te explique cómo descargarlo del portal?*

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REGLAS DE ORO
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
- Responde SIEMPRE en español, con lenguaje cercano y empático.
- Usa EXCLUSIVAMENTE el contexto documental recuperado para responder.
- Tienes prohibido usar conocimiento externo, memoria general del modelo o informacion de internet.
- Nunca inventes artículos, fechas ni procedimientos.
- Si la evidencia recuperada es insuficiente, dilo con honestidad y sugiere dónde buscar.
- Usa los marcadores [1], [2], etc. para referenciar los fragmentos del contexto.
- No uses jerga burocrática innecesaria.
- Devuelve SOLO JSON válido con las claves indicadas.
"""


class WriterAgent:
    def __init__(self, settings: Settings, llm_client: LLMClient, crew_llm=None) -> None:
        self.settings = settings
        self.llm_client = llm_client
        self.crewai_agent = self._build_crewai_agent(crew_llm)

    def _build_crewai_agent(self, crew_llm):
        llm = crew_llm or build_crewai_llm(self.settings)
        if llm is None:
            return None
        return Agent(
            role="Asesor Estudiantil Digital UdeA",
            goal=(
                "Traducir la normativa universitaria densa en explicaciones claras, empáticas "
                "y accionables para estudiantes, citando siempre la fuente documental exacta "
                "y cerrando con una pregunta de seguimiento que anticipe el próximo paso del trámite."
            ),
            backstory=(
                "Eres el asesor universitario más cercano que existe. Llevas años ayudando a "
                "estudiantes de la UdeA a navegar reglamentos, matrículas, cancelaciones, "
                "homologaciones y recursos. Conoces cada artículo del Reglamento Estudiantil "
                "pero nunca lo citas textualmente sin antes explicarlo en palabras simples. "
                "Tu superpoder es convertir el lenguaje burocrático en pasos concretos y comprensibles."
            ),
            llm=llm,
            verbose=False,
        )

    @staticmethod
    def _format_chat_history(chat_history: list[dict[str, str]] | None) -> str:
        if not chat_history:
            return "Sin historial previo."
        formatted: list[str] = []
        for message in chat_history[-8:]:
            role = str(message.get("role", "user")).lower().strip()
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            role_label = "Estudiante" if role == "user" else "Asesor"
            formatted.append(f"{role_label}: {content}")
        return "\n".join(formatted) if formatted else "Sin historial previo."

    def draft_answer(
        self,
        question: str,
        intent: QuestionIntent,
        context: str,
        hits: list[RetrievalHit],
        chat_history: list[dict[str, str]] | None = None,
    ) -> AnswerPayload:
        sources_summary = "\n".join(
            f"[{index}] {hit.source_name} | p. {hit.page_number or 'N/A'} | score={hit.score:.3f}"
            for index, hit in enumerate(hits, start=1)
        )
        prompt = f"""
Pregunta del estudiante:
{question}

Intención detectada:
{intent.model_dump_json(indent=2)}

Historial reciente de la conversación:
{self._format_chat_history(chat_history)}

Contexto documental recuperado (usa estos fragmentos como tu única fuente de verdad):
{context}

Fuentes disponibles:
{sources_summary}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
INSTRUCCIONES DE FORMATO DE SALIDA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Devuelve UN ÚNICO objeto JSON válido con exactamente estas claves:

- "answer": string — tu respuesta completa en español. Debe incluir:
    • Contexto breve (1-2 oraciones)
    • Pasos accionables o viñetas claras
    • Citas de fuente obligatorias entre paréntesis: (Según el Artículo X de [Documento])
    • Alerta de plazo con ⚠️ si aplica
    • Pregunta de cierre en cursiva al final (usa *texto en cursiva*)

- "confidence": número entre 0.0 y 1.0 que refleja qué tan completa es la evidencia documental.

- "documents_used": lista de strings con los nombres de los documentos fuente usados.

- "notes": lista de strings con observaciones importantes o limitaciones de la respuesta.

Reglas:
- Si la evidencia no alcanza para responder, NO inventes y responde explicitamente que no hay informacion suficiente.
- Usa [1], [2] para referenciar los fragmentos cuando sea pertinente.
- NO incluyas claves adicionales en el JSON.
- La pregunta de cierre va dentro del campo "answer", al final, en cursiva.
"""
        try:
            payload = self.llm_client.complete_json(prompt=prompt, system_prompt=_SYSTEM_PROMPT)
            answer_text = str(payload.get("answer", "")).strip()
            if not answer_text:
                return self._fallback_answer(question=question, intent=intent, hits=hits)
            documents_used = payload.get("documents_used") or [hit.source_name for hit in hits]
            notes = payload.get("notes") or []
            answer_text = self._append_references(answer_text, hits)
            return AnswerPayload(
                answer=answer_text,
                intent=intent,
                confidence=float(payload.get("confidence", 0.0) or 0.0),
                documents_used=[str(document) for document in documents_used],
                sources=hits,
                notes=[str(note) for note in notes],
            )
        except Exception as exc:
            logger.exception("Falló el agente redactor")
            fallback = self._fallback_answer(question=question, intent=intent, hits=hits)
            fallback.notes.append(f"Contingencia activada por error LLM: {exc}")
            return fallback

    @staticmethod
    def _append_references(answer_text: str, hits: list[RetrievalHit]) -> str:
        if not hits:
            return answer_text

        if "referencias" in answer_text.lower():
            return answer_text

        lines: list[str] = []
        for idx, hit in enumerate(hits[:3], start=1):
            page_label = f"p. {hit.page_number}" if hit.page_number else "pág. no identificada"
            lines.append(f"- [{idx}] {hit.source_name} ({page_label})")

        references_block = "\n\nReferencias de PDFs consultados:\n" + "\n".join(lines)
        return answer_text.rstrip() + references_block

    def _fallback_answer(self, question: str, intent: QuestionIntent, hits: list[RetrievalHit]) -> AnswerPayload:
        if not hits:
            return AnswerPayload(
                answer=(
                    "No encontré evidencia documental suficiente para responderte con precisión. "
                    "Te recomiendo reformular la pregunta o verificar que los documentos estén indexados.\n\n"
                    "*¿Quieres intentar con otra pregunta o necesitas ayuda para indexar los documentos?*"
                ),
                intent=intent,
                confidence=0.2,
                documents_used=[],
                sources=[],
                notes=["Respuesta de contingencia sin proveedor LLM."],
            )

        lines = []
        for index, hit in enumerate(hits[:3], start=1):
            snippet = " ".join(hit.text.strip().split())[:220]
            lines.append(
                f"[{index}] (Según {hit.source_name}, p. {hit.page_number or 'N/A'}): {snippet}"
            )

        answer = (
            "Aquí encontré información relevante en los documentos disponibles:\n\n"
            + "\n\n".join(lines)
            + "\n\n⚠️ Nota: esta respuesta se generó en modo local de contingencia (sin LLM externo), "
            "por lo que no está traducida al lenguaje coloquial."
            "\n\n*¿Te gustaría que profundice en alguno de estos puntos cuando el servicio LLM esté disponible?*"
        )
        return AnswerPayload(
            answer=answer,
            intent=intent,
            confidence=0.45,
            documents_used=[hit.source_name for hit in hits],
            sources=hits,
            notes=["Respuesta de contingencia sin proveedor LLM."],
        )
