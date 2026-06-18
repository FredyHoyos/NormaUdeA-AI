"""Punto de entrada principal — Copiloto Administrativo Agéntico UdeA.

Integra:
- Frontend institucional UdeA (CSS, paleta, tipografía).
- Preguntas sugeridas en cold-start (inyección automática al flujo).
- Registro analítico de interacciones (SQLite).
- Sidebar con configuración y métricas de uso.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Garantiza que la raíz del proyecto esté en sys.path cuando Streamlit
# arranca desde app/main.py (Streamlit añade app/ pero no la raíz).
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
    render_ingestion_summary,
    render_suggested_questions,
    render_welcome_banner,
)

logger = logging.getLogger(__name__)
_MAX_CHAT_MEMORY_MESSAGES = 10

# ── Preguntas frecuentes para el cold-start ──────────────────────────────────
SUGGESTED_QUESTIONS: list[str] = [
    "¿Cómo solicito una cancelación de matrícula?",
    "¿Cuáles son los requisitos para una homologación de materias?",
    "¿Qué debo hacer si repruebo una materia por tercera vez?",
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
    """Procesa una pregunta (del input o de un botón sugerido) y renderiza la respuesta."""
    st.session_state.messages.append({"role": "user", "content": question})
    chat_history = st.session_state.messages[-_MAX_CHAT_MEMORY_MESSAGES:]

    with st.chat_message("user"):
        st.markdown(question)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Consultando documentos y redactando respuesta…"):
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

    # ── Estilos institucionales UdeA ─────────────────────────────────────────
    inject_udea_styles()

    # ── Header ───────────────────────────────────────────────────────────────
    st.markdown(
        "<h1 style='margin-bottom:0'>🎓 Copiloto Administrativo UdeA</h1>",
        unsafe_allow_html=True,
    )
    st.caption(
        "Asesor estudiantil digital · Normas, reglamentos y procedimientos académicos · "
        "Universidad de Antioquia"
    )

    try:
        service = get_service()
    except Exception as exc:
        logger.warning("Error crítico al inicializar servicio: %s", exc)
        service = None

    # Si el servicio no pudo inicializarse, mostrar aviso pero NO crashear
    if service is None:
        st.warning(
            "⚠️ **Modo sin LLM activo** — No se detectó un proveedor de IA configurado.\n\n"
            "La interfaz carga correctamente. Para habilitar respuestas completas, configura "
            "en tu `.env`: `GEMINI_API_KEY`, `OPENAI_API_KEY` o levanta Ollama localmente."
        )

    # ── Sidebar institucional ─────────────────────────────────────────────────
    with st.sidebar:
        st.markdown(
            """
            <div style="text-align:center;padding:1rem 0 0.5rem 0;">
              <span style="font-size:3rem;">🎓</span><br>
              <strong style="font-size:1.1rem;">NormaUdeA-AI</strong><br>
              <span style="font-size:0.78rem;opacity:0.85;">Copiloto Administrativo Agéntico</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()

        st.markdown("**⚙️ Configuración**")
        st.write(f"🤖 Proveedor LLM: `{settings.llm_provider}`")
        st.write(f"📦 Colección: `{settings.chroma_collection}`")
        st.write(f"📁 PDFs: `{settings.pdf_dir}`")

        st.divider()

        if st.button("📥 Indexar PDFs locales", type="primary"):
            progress_bar = st.progress(0)
            progress_status = st.empty()

            def on_progress(progress: IngestionProgress) -> None:
                progress_bar.progress(int(progress.progress_percent))
                progress_status.info(
                    f"{progress.message} | "
                    f"Archivos: {progress.files_processed}/{progress.total_files} | "
                    f"Chunks: {progress.chunks_indexed}"
                )

            with st.spinner("Indexando documentos locales…"):
                summary = service.index_documents(progress_callback=on_progress)
            progress_bar.progress(100)
            progress_status.success(
                f"✅ Finalizado | Archivos: {summary.files_processed} | Chunks: {summary.chunks_indexed}"
            )
            render_ingestion_summary(summary)

        st.divider()

        # ── Estadísticas de uso (SQLite) ─────────────────────────────────────
        st.markdown("**📊 Estadísticas de uso**")
        try:
            stats = service.logger.get_stats()
            if stats and stats.get("total_queries"):
                st.metric("Consultas totales", stats.get("total_queries", 0))
                st.metric("Confianza promedio", f"{float(stats.get('avg_confidence', 0)):.0%}")
                st.metric("Tiempo promedio", f"{float(stats.get('avg_time_ms', 0)) / 1000:.1f} s")
            else:
                st.caption("Aún no hay consultas registradas.")
        except Exception:
            st.caption("Estadísticas no disponibles.")

        st.divider()
        st.caption("Powered by CrewAI · ChromaDB · Streamlit")

    # ── Estado del chat ───────────────────────────────────────────────────────
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None

    # ── Cold Start: banner + preguntas sugeridas ──────────────────────────────
    if not st.session_state.messages:
        render_welcome_banner()
        clicked = render_suggested_questions(SUGGESTED_QUESTIONS)
        if clicked and service is not None:
            st.session_state.pending_question = clicked
            st.rerun()
        elif clicked and service is None:
            st.info("Configura un proveedor LLM en `.env` para responder preguntas.")

    # ── Renderizar historial de mensajes ──────────────────────────────────────
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    # ── Procesar pregunta pendiente (de botón sugerido) ───────────────────────
    if st.session_state.pending_question and service is not None:
        question = st.session_state.pending_question
        st.session_state.pending_question = None
        _process_question(question, service)
        st.rerun()

    # ── Input de chat ─────────────────────────────────────────────────────────
    question = st.chat_input("Escribe tu pregunta sobre reglamentos, trámites o normas académicas…")
    if question and service is not None:
        _process_question(question, service)
    elif question and service is None:
        st.warning("Sin LLM configurado. Configura `GEMINI_API_KEY` u `OPENAI_API_KEY` en `.env`.")


if __name__ == "__main__":
    main()
