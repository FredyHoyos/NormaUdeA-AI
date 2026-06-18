from __future__ import annotations

import json
import logging
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
        if self.crew_llm is not None and self._agents_ready():
            try:
                return self._answer_with_crew(question, chat_history)
            except Exception as exc:
                logger.warning("CrewAI fallo (%s), usando orquestacion directa", exc)
        return self._answer_direct(question, chat_history)

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

    def _answer_direct(self, question: str, chat_history: list[dict[str, str]] | None = None) -> AnswerPayload:
        intent = self.classifier_agent.classify(question, chat_history=chat_history)
        hits = self.retriever_agent.recover(question) if intent.needs_retrieval else []
        context = self.retriever.build_context(hits)
        answer = self.writer_agent.draft_answer(question, intent, context, hits, chat_history=chat_history)
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