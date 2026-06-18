"""Punto de entrada principal - Copiloto Administrativo Agentico UdeA.

Integra:
- Frontend institucional UdeA (CSS, paleta, tipografia).
- Preguntas sugeridas en cold-start (inyeccion automatica al flujo).
- Registro analitico de interacciones (SQLite).
- Sidebar con configuracion y metricas de uso.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Garantiza que la raiz del proyecto este en sys.path cuando Streamlit
# arranca desde app/main.py (Streamlit anade app/ pero no la raiz).
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

import streamlit as st

from app.agents.manager import CrewAIManager
from app.config.settings import get_settings
from app.core.logging_config import configure_logging
from app.models import IngestionProgress
from app.services.answer_service import AnswerService
from app.ui.components import (
    inject_udea_styles,
    render_answer,
    render_header_with_logo,
    render_ingestion_summary,
    render_sidebar_logo,
    render_suggested_questions,
    render_welcome_banner,
)

logger = logging.getLogger(__name__)
_MAX_CHAT_MEMORY_MESSAGES = 10

# Preguntas frecuentes para el cold-start
SUGGESTED_QUESTIONS: list[str] = [
    "Como solicito una cancelacion de matricula?",
    "Cuales son los requisitos para una homologacion de materias?",
    "Que debo hacer si repruebo una materia por tercera vez?",
]


@st.cache_resource(show_spinner=False)
def get_service() -> AnswerService | None:
    try:
        settings = get_settings()
        configure_logging(settings.logs_dir)
        manager = CrewAIManager(settings)
        return AnswerService(manager)
    except Exception as exc:
        logger.warning("Error al inicializar el servicio: %s", exc)
        return None


def _process_question(question: str, service: AnswerService) -> None:
    """Procesa una pregunta (del input o de un boton sugerido) y renderiza la respuesta."""
    st.session_state.messages.append({"role": "user", "content": question})
    chat_history = st.session_state.messages[-_MAX_CHAT_MEMORY_MESSAGES:]

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("Consultando documentos y redactando respuesta..."):
            answer = service.answer(question, chat_history=chat_history)
        render_answer(answer)
        st.session_state.messages.append({"role": "assistant", "content": answer.answer})


def main() -> None:
    settings = get_settings()
    st.set_page_config(
        page_title=settings.streamlit_page_title,
        page_icon=settings.streamlit_page_icon,
        layout="wide",
        initial_sidebar_state="expanded",
    )

    inject_udea_styles()
    render_header_with_logo()

    try:
        service = get_service()
    except Exception as exc:
        logger.warning("Error critico al inicializar servicio: %s", exc)
        service = None

    if service is None:
        st.warning(
            "Servicio incompleto: falta configuracion de LLM o fuente documental.\n\n"
            "Configura en tu .env:\n"
            "- SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY\n"
            "- GEMINI_API_KEY u OPENAI_API_KEY, o levanta Ollama localmente."
        )

    with st.sidebar:
        render_sidebar_logo()
        st.divider()

        st.markdown("**Configuracion**")
        st.write(f"Proveedor LLM: `{settings.llm_provider}`")
        st.write(f"Coleccion: `{settings.chroma_collection}`")
        st.write(f"Tabla Supabase: `{settings.supabase_table}`")
        current_chunks = service.indexed_chunks_count() if service is not None else 0
        st.write(f"Chunks actuales en indice: `{current_chunks}`")
        if current_chunks > 0:
            st.caption("No necesitas reindexar al reiniciar si los documentos no cambiaron.")

        st.divider()

        if st.button("Indexar PDFs desde Supabase", type="primary"):
            if service is None:
                st.warning("Configura Supabase y LLM en .env antes de indexar documentos.")
                st.stop()

            progress_bar = st.progress(0)
            progress_status = st.empty()

            def on_progress(progress: IngestionProgress) -> None:
                progress_bar.progress(int(progress.progress_percent))
                progress_status.info(
                    f"{progress.message} | "
                    f"Archivos: {progress.files_processed}/{progress.total_files} | "
                    f"Chunks: {progress.chunks_indexed}"
                )

            with st.spinner("Indexando documentos desde Supabase..."):
                summary = service.index_documents(progress_callback=on_progress)
            progress_bar.progress(100)
            progress_status.success(
                f"Finalizado | Archivos nuevos/actualizados: {summary.files_processed} | "
                f"Reutilizados: {summary.reused_files} | Chunks: {summary.chunks_indexed}"
            )
            render_ingestion_summary(summary)

        st.divider()

        st.markdown("**Estadisticas de uso**")
        try:
            stats = service.logger.get_stats() if service is not None else {}
            if stats and stats.get("total_queries"):
                st.metric("Consultas totales", stats.get("total_queries", 0))
                st.metric("Confianza promedio", f"{float(stats.get('avg_confidence', 0)):.0%}")
                st.metric("Tiempo promedio", f"{float(stats.get('avg_time_ms', 0)) / 1000:.1f} s")
            else:
                st.caption("Aun no hay consultas registradas.")
        except Exception:
            st.caption("Estadisticas no disponibles.")

        st.divider()
        st.caption("Powered by CrewAI - ChromaDB - Streamlit")

    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None

    if not st.session_state.messages:
        render_welcome_banner()
        clicked = render_suggested_questions(SUGGESTED_QUESTIONS)
        if clicked and service is not None:
            st.session_state.pending_question = clicked
            st.rerun()
        elif clicked and service is None:
            st.info("Configura un proveedor LLM en .env para responder preguntas.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if st.session_state.pending_question and service is not None:
        question = st.session_state.pending_question
        st.session_state.pending_question = None
        _process_question(question, service)
        st.rerun()

    question = st.chat_input("Escribe tu pregunta sobre reglamentos, tramites o normas academicas...")
    if question and service is not None:
        _process_question(question, service)
    elif question and service is None:
        st.warning("Sin LLM configurado. Configura GEMINI_API_KEY u OPENAI_API_KEY en .env.")


if __name__ == "__main__":
    main()