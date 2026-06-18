from __future__ import annotations

import json
import logging
import re
from collections.abc import Callable
from pathlib import Path

from crewai import Crew, Process, Task

from app.agents.classifier import IntentClassifierAgent
from app.agents.retriever_agent import RetrieverAgent
from app.agents.writer_agent import WriterAgent
from app.config.settings import Settings
from app.domain.supabase_pdf_source import SupabasePDFSource
from app.llm.client import LLMClient
from app.llm.crewai_adapter import build_crewai_llm
from app.models import AnswerPayload, IngestionProgress, IngestionSummary, QuestionIntent, RetrievalHit
from app.retrieval.retriever import Retriever
from app.vectorstore.chroma_store import ChromaKnowledgeBase

logger = logging.getLogger(__name__)


class CrewAIManager:
    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or Settings()
        self.llm_client = LLMClient(self.settings)
        self.knowledge_base = ChromaKnowledgeBase(self.settings)
        self.document_source = SupabasePDFSource(self.settings, self.knowledge_base)
        self.retriever = Retriever(self.document_source, self.settings, llm_client=self.llm_client)
        self.crew_llm = build_crewai_llm(self.settings)
        self.classifier_agent = IntentClassifierAgent(self.settings, self.llm_client, crew_llm=self.crew_llm)
        self.retriever_agent = RetrieverAgent(self.settings, self.retriever, crew_llm=self.crew_llm)
        self.writer_agent = WriterAgent(self.settings, self.llm_client, crew_llm=self.crew_llm)

    def index_local_pdfs(
        self,
        pdf_dir: Path | None = None,
        progress_callback: Callable[[IngestionProgress], None] | None = None,
    ) -> IngestionSummary:
        _ = pdf_dir
        return self.document_source.index_directory(progress_callback=progress_callback)

    def indexed_chunks_count(self) -> int:
        return self.knowledge_base.count_all()

    def answer(self, question: str, chat_history: list[dict[str, str]] | None = None) -> AnswerPayload:
        intent = self.classifier_agent.classify(question, chat_history=chat_history)

        if self._should_force_retrieval(question):
            intent.needs_retrieval = True

        if not intent.needs_retrieval:
            return self._answer_conversational(question, intent, chat_history)

        if self.settings.strict_rag_only:
            return self._answer_direct(question, intent, chat_history)

        if self.crew_llm is not None and self._agents_ready():
            try:
                return self._answer_with_crew(question, chat_history)
            except Exception as exc:
                logger.warning("CrewAI fallo (%s), usando orquestacion directa", exc)
        return self._answer_direct(question, intent, chat_history)

    def _agents_ready(self) -> bool:
        return all([
            getattr(self.classifier_agent, "crewai_agent", None) is not None,
            getattr(self.retriever_agent, "crewai_agent", None) is not None,
            getattr(self.writer_agent, "crewai_agent", None) is not None,
        ])

    def _answer_with_crew(self, question: str, chat_history: list[dict[str, str]] | None = None) -> AnswerPayload:
        chat_text = self._format_chat_history_for_task(chat_history)

        classify_task = Task(
            description=f"""Clasifica la intencion de la siguiente consulta universitaria.

Consulta: {question}

Historial conversacional:
{chat_text}

Categorias posibles: academic, administrative, regulation, procedures, general, other.
Determina si la consulta necesita busqueda documental (needs_retrieval).
Devuelve un JSON con: category, needs_retrieval, confidence, rationale.""",
            expected_output="""JSON con las siguientes claves:
- category: string (academic, administrative, regulation, procedures, general, other)
- needs_retrieval: boolean
- confidence: float entre 0 y 1
- rationale: string explicativo""",
            agent=self.classifier_agent.crewai_agent,
            output_pydantic=QuestionIntent,
        )

        retrieve_task = Task(
            description=f"""Busca documentos relevantes para responder la consulta.

Consulta original: {question}

Usa la herramienta 'Buscar Documentos' para encontrar fragmentos relevantes en la base documental.
Presenta los resultados de forma clara indicando fuente, pagina y puntuacion de relevancia.""",
            expected_output="Fragmentos documentales relevantes con fuente, numero de pagina y puntuacion de relevancia",
            agent=self.retriever_agent.crewai_agent,
            context=[classify_task],
        )

        write_task = Task(
            description=f"""Redacta una respuesta final para la consulta.

Consulta original: {question}

Basate en la clasificacion de intencion y los documentos recuperados en las tareas anteriores.
Responde en espanol, usa referencias a las fuentes como [1], [2] cuando sea pertinente.
Si la evidencia no alcanza para responder completamente, indicalo claramente.

Historial conversacional:
{chat_text}

Devuelve un JSON con:
- answer: respuesta en espanol
- confidence: numero entre 0 y 1
- documents_used: lista de nombres de documentos fuente
- notes: lista de observaciones""",
            expected_output="""JSON con las siguientes claves:
- answer: string (respuesta en espanol)
- confidence: float entre 0 y 1
- documents_used: list de strings (nombres de documentos)
- notes: list de strings""",
            agent=self.writer_agent.crewai_agent,
            context=[classify_task, retrieve_task],
            output_pydantic=AnswerPayload,
        )

        crew = Crew(
            agents=[
                self.classifier_agent.crewai_agent,
                self.retriever_agent.crewai_agent,
                self.writer_agent.crewai_agent,
            ],
            tasks=[classify_task, retrieve_task, write_task],
            process=Process.sequential,
            verbose=False,
        )

        result = crew.kickoff()

        return self._parse_crew_result(result, classify_task, retrieve_task, write_task)

    def _parse_crew_result(
        self,
        result,
        classify_task: Task,
        retrieve_task: Task,
        write_task: Task,
    ) -> AnswerPayload:
        intent = None
        hits: list[RetrievalHit] = []
        answer_payload = None

        if write_task.output is not None and write_task.output.pydantic is not None:
            answer_payload = write_task.output.pydantic
        elif classify_task.output is not None and classify_task.output.pydantic is not None:
            intent = classify_task.output.pydantic
        elif result and hasattr(result, "raw") and result.raw:
            answer_payload = self._try_parse_json(str(result.raw))

        if answer_payload is None:
            intent = intent or QuestionIntent(category="general", needs_retrieval=True, confidence=0.0)
            return AnswerPayload(
                answer="No se pudo generar una respuesta. Intenta reformular la pregunta.",
                intent=intent,
                confidence=0.0,
                documents_used=[],
                sources=[],
                notes=["CrewAI no produjo una respuesta valida."],
            )

        if isinstance(answer_payload, AnswerPayload):
            if answer_payload.intent.category == "general" and intent is not None:
                answer_payload.intent = intent
            if not answer_payload.sources:
                answer_payload.sources = hits
            answer_payload.confidence = self._final_confidence(answer_payload, answer_payload.sources, answer_payload.intent)
            return answer_payload

        intent = intent or QuestionIntent(category="general", needs_retrieval=True, confidence=0.0)
        return AnswerPayload(
            answer=str(answer_payload),
            intent=intent,
            confidence=0.0,
            documents_used=[],
            sources=[],
            notes=["Respuesta generada por CrewAI en modo texto plano."],
        )

    def _try_parse_json(self, text: str) -> AnswerPayload | None:
        try:
            data = json.loads(text)
            if isinstance(data, dict) and "answer" in data:
                return AnswerPayload(
                    answer=str(data["answer"]),
                    intent=QuestionIntent(),
                    confidence=float(data.get("confidence", 0.0) or 0.0),
                    documents_used=[str(d) for d in data.get("documents_used", [])],
                    notes=[str(n) for n in data.get("notes", [])],
                )
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
        return None

    def _answer_conversational(self, question: str, intent: QuestionIntent, chat_history: list[dict[str, str]] | None = None) -> AnswerPayload:
        history = self._format_chat_history_for_task(chat_history)
        prompt = f"""
Historial de la conversacion:
{history}

Pregunta del usuario: {question}

Responde de forma natural, amigable y conversacional en español.
"""
        system = (
            "Eres el Asesor Estudiantil Digital de la Universidad de Antioquia. "
            "Eres amigable, cercano y respondes en español. "
            "Cuando te saluden, agradezcan o se despidan, responde de forma cordial. "
            "Cuando pregunten algo general sobre la universidad, responde con lo que sepas "
            "y sugiere buscar en los documentos para informacion mas precisa. "
            "No inventes citas ni referencias a documentos."
        )
        try:
            response = self.llm_client.complete(prompt=prompt, system_prompt=system)
            answer_text = response.text.strip() or "¿En qué puedo ayudarte hoy?"
            return AnswerPayload(
                answer=answer_text,
                intent=intent,
                confidence=0.9,
                notes=["Respuesta conversacional sin recuperacion documental."],
            )
        except Exception as exc:
            logger.exception("Falló la respuesta conversacional")
            return AnswerPayload(
                answer="¿En qué puedo ayudarte hoy?",
                intent=intent,
                confidence=0.5,
                notes=[f"Respuesta conversacional de contingencia: {exc}"],
            )

    def _answer_direct(self, question: str, intent: QuestionIntent, chat_history: list[dict[str, str]] | None = None) -> AnswerPayload:
        hits = self.retriever_agent.recover(question) if intent.needs_retrieval else []
        hits = self._select_grounded_hits(hits)
        if intent.needs_retrieval and not hits:
            return self._insufficient_evidence_payload(intent)

        context = self.retriever.build_context(hits)
        answer = self.writer_agent.draft_answer(question, intent, context, hits, chat_history=chat_history)
        answer.sources = hits
        answer.documents_used = list(dict.fromkeys(hit.source_name for hit in hits))
        answer.confidence = self._final_confidence(answer, hits, intent)
        return answer

    def _insufficient_evidence_payload(self, intent: QuestionIntent) -> AnswerPayload:
        return AnswerPayload(
            answer=(
                "No hay informacion documental suficiente en los PDFs indexados para responder esa pregunta con precision. "
                "Si quieres, puedo intentarlo de nuevo con una pregunta mas especifica o con mas documentos indexados."
            ),
            intent=intent,
            confidence=0.15,
            documents_used=[],
            sources=[],
            notes=["Respuesta bloqueada por modo RAG estricto: sin evidencia documental suficiente."],
        )

    def _select_grounded_hits(self, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        if not hits:
            return []

        min_score = max(0.0, min(1.0, float(self.settings.strict_rag_min_score)))
        filtered = [hit for hit in hits if hit.score >= min_score]

        if len(filtered) < max(1, int(self.settings.strict_rag_min_hits)):
            return []

        return filtered[: self.settings.retrieval_k]

    def _should_force_retrieval(self, question: str) -> bool:
        if not self.settings.strict_rag_only:
            return False
        return not self._is_small_talk(question)

    @staticmethod
    def _is_small_talk(question: str) -> bool:
        text = question.strip().lower()
        if not text:
            return True

        patterns = [
            r"^hola[!. ]*$",
            r"^buen(as|os)?\s+(dias|tardes|noches)[!. ]*$",
            r"^gracias[!. ]*$",
            r"^muchas\s+gracias[!. ]*$",
            r"^ok(ay)?[!. ]*$",
            r"^listo[!. ]*$",
            r"^entiendo[!. ]*$",
            r"^adios[!. ]*$",
            r"^chao[!. ]*$",
            r"^hasta\s+luego[!. ]*$",
        ]
        return any(re.fullmatch(pattern, text) for pattern in patterns)

    def _final_confidence(self, answer: AnswerPayload, hits: list, intent) -> float:
        if not hits:
            return min(0.35, answer.confidence or 0.2)
        top_score = max((hit.score for hit in hits), default=0.0)
        coverage = min(1.0, len({hit.source_name for hit in hits}) / 3.0)
        intent_score = float(getattr(intent, "confidence", 0.0) or 0.0)
        combined = (0.55 * top_score) + (0.25 * coverage) + (0.20 * intent_score)
        return round(max(answer.confidence, combined), 3)

    @staticmethod
    def _format_chat_history_for_task(chat_history: list[dict[str, str]] | None) -> str:
        if not chat_history:
            return "Sin historial previo."
        formatted: list[str] = []
        for message in chat_history[-8:]:
            role = str(message.get("role", "user")).lower().strip()
            content = str(message.get("content", "")).strip()
            if not content:
                continue
            role_label = "Usuario" if role == "user" else "Asistente"
            formatted.append(f"{role_label}: {content}")
        return "\n".join(formatted) if formatted else "Sin historial previo."