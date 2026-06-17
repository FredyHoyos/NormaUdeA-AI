from __future__ import annotations

import streamlit as st

from app.models import AnswerPayload, IngestionSummary


def render_ingestion_summary(summary: IngestionSummary) -> None:
    st.subheader("Estado de indexacion")
    cols = st.columns(3)
    cols[0].metric("Archivos procesados", summary.files_processed)
    cols[1].metric("Chunks indexados", summary.chunks_indexed)
    cols[2].metric("Errores", len(summary.errors))
    if summary.errors:
        st.warning("\n".join(summary.errors))


def render_answer(answer: AnswerPayload) -> None:
    st.markdown(answer.answer)
    cols = st.columns(3)
    cols[0].metric("Confianza", f"{answer.confidence:.2f}")
    cols[1].metric("Documentos usados", len(answer.documents_used))
    cols[2].metric("Fragmentos", len(answer.sources))

    if answer.documents_used:
        st.markdown("**Documentos usados**")
        for document in answer.documents_used:
            st.write(f"- {document}")

    if answer.sources:
        st.markdown("**Articulos / fragmentos encontrados**")
        for index, source in enumerate(answer.sources, start=1):
            page_label = f"p. {source.page_number}" if source.page_number else "pagina no identificada"
            st.write(f"[{index}] {source.source_name} - {page_label} - score {source.score:.3f}")
            st.caption(source.text[:600] + ("..." if len(source.text) > 600 else ""))

    if answer.notes:
        st.info("\n".join(answer.notes))
