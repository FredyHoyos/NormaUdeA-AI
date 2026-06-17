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
from app.ui.components import render_answer, render_ingestion_summary

logger = logging.getLogger(__name__)


def get_service() -> AnswerService:
    settings = get_settings()
    configure_logging(settings.logs_dir)
    manager = CrewAIManager(settings)
    return AnswerService(manager)


def main() -> None:
    settings = get_settings()
    st.set_page_config(page_title=settings.streamlit_page_title, page_icon=settings.streamlit_page_icon, layout="wide")
    st.title(settings.app_name)
    st.caption("Copiloto administrativo agéntico para consultas sobre PDFs locales de la Universidad de Antioquia.")

    service = get_service()

    with st.sidebar:
        st.header("Configuracion")
        st.write(f"Proveedor LLM: {settings.llm_provider}")
        st.write(f"Coleccion Chroma: {settings.chroma_collection}")
        st.write(f"Carpeta PDFs: {settings.pdf_dir}")
        st.write(f"Base vectorial: {settings.chroma_dir}")

        if st.button("Indexar PDFs locales", type="primary"):
            progress_bar = st.progress(0)
            progress_status = st.empty()

            def on_progress(progress: IngestionProgress) -> None:
                progress_bar.progress(int(progress.progress_percent))
                progress_status.info(
                    f"{progress.message} | Archivos: {progress.files_processed}/{progress.total_files} | "
                    f"Chunks: {progress.chunks_indexed}"
                )

            with st.spinner("Indexando documentos locales..."):
                summary = service.index_documents(progress_callback=on_progress)
            progress_bar.progress(100)
            progress_status.success(
                f"Indexacion finalizada | Archivos: {summary.files_processed} | Chunks: {summary.chunks_indexed}"
            )
            st.success("Indexacion completada")
            render_ingestion_summary(summary)

    if "messages" not in st.session_state:
        st.session_state.messages = []

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    question = st.chat_input("Escribe tu pregunta sobre reglamentos, tramites o normas academicas")
    if question:
        st.session_state.messages.append({"role": "user", "content": question})
        with st.chat_message("user"):
            st.markdown(question)

        with st.chat_message("assistant"):
            with st.spinner("Consultando documentos y redactando respuesta..."):
                answer = service.answer(question)
            render_answer(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer.answer})


if __name__ == "__main__":
    main()
