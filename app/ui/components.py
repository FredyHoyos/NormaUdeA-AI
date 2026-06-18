"""Componentes UI institucionales UdeA para Streamlit.

Incluye:
- inject_udea_styles(): inyecta CSS con paleta oficial UdeA.
- render_suggested_questions(): pills de preguntas frecuentes (cold start).
- render_answer(): card principal + expander de auditoría con badges.
- render_ingestion_summary(): métricas de indexación.
- render_audit_badges(): indicadores de confianza con semáforo de color.
"""

from __future__ import annotations

import streamlit as st

from app.models import AnswerPayload, IngestionSummary

# ── Paleta oficial UdeA ──────────────────────────────────────────────────────
_UDEA_GREEN      = "#1B5E20"
_UDEA_GREEN_MID  = "#2E7D32"
_UDEA_GREEN_LITE = "#43A047"
_UDEA_GREEN_BG   = "#E8F5E9"
_UDEA_WHITE      = "#FFFFFF"
_UDEA_GRAY_DARK  = "#212121"
_UDEA_GRAY_MID   = "#424242"
_UDEA_GRAY_LITE  = "#F5F5F5"
_UDEA_GOLD       = "#F9A825"
_UDEA_RED        = "#C62828"

# ── CSS institucional completo ───────────────────────────────────────────────
_UDEA_CSS = f"""
<style>
  /* ── Google Fonts ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  /* ── Variables ── */
  :root {{
    --udea-green:      {_UDEA_GREEN};
    --udea-green-mid:  {_UDEA_GREEN_MID};
    --udea-green-lite: {_UDEA_GREEN_LITE};
    --udea-green-bg:   {_UDEA_GREEN_BG};
    --udea-white:      {_UDEA_WHITE};
    --udea-gray-dark:  {_UDEA_GRAY_DARK};
    --udea-gray-mid:   {_UDEA_GRAY_MID};
    --udea-gray-lite:  {_UDEA_GRAY_LITE};
    --udea-gold:       {_UDEA_GOLD};
    --udea-red:        {_UDEA_RED};
    --radius:          12px;
    --shadow:          0 4px 20px rgba(0,0,0,0.08);
    --shadow-hover:    0 8px 32px rgba(27,94,32,0.18);
    --transition:      0.22s cubic-bezier(.4,0,.2,1);
  }}

  /* ── Base ── */
  html, body, [class*="css"] {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
    color: var(--udea-gray-dark);
  }}

  /* ── App header ── */
  .main .block-container {{
    padding-top: 1.5rem;
    max-width: 900px;
  }}

  /* ── Título principal ── */
  h1 {{
    background: linear-gradient(135deg, var(--udea-green) 0%, var(--udea-green-lite) 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-weight: 700 !important;
    font-size: 1.9rem !important;
    letter-spacing: -0.5px;
    margin-bottom: 0.1rem !important;
  }}

  /* ── Sidebar ── */
  [data-testid="stSidebar"] {{
    background: linear-gradient(180deg, var(--udea-green) 0%, var(--udea-green-mid) 100%) !important;
    color: white !important;
    border-right: none !important;
  }}
  [data-testid="stSidebar"] * {{
    color: white !important;
  }}
  [data-testid="stSidebar"] .stButton > button {{
    background: rgba(255,255,255,0.15) !important;
    border: 1.5px solid rgba(255,255,255,0.5) !important;
    color: white !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    transition: var(--transition) !important;
    width: 100%;
  }}
  [data-testid="stSidebar"] .stButton > button:hover {{
    background: rgba(255,255,255,0.28) !important;
    transform: translateY(-1px);
  }}

  /* ── Suggested question pills ── */
  .udea-pill-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    margin: 1.2rem 0 1.6rem 0;
  }}
  .udea-pill-btn {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    background: var(--udea-green-bg);
    border: 1.5px solid var(--udea-green-lite);
    color: var(--udea-green) !important;
    border-radius: 24px;
    padding: 8px 18px;
    font-size: 0.88rem;
    font-weight: 600;
    cursor: pointer;
    transition: var(--transition);
    text-decoration: none;
    white-space: nowrap;
  }}
  .udea-pill-btn:hover {{
    background: var(--udea-green);
    color: white !important;
    border-color: var(--udea-green);
    transform: translateY(-2px);
    box-shadow: var(--shadow-hover);
  }}

  /* ── Botones de preguntas sugeridas en Streamlit ── */
  div[data-testid="stHorizontalBlock"] .stButton > button[kind="secondary"] {{
    background: var(--udea-green-bg) !important;
    border: 1.5px solid var(--udea-green-lite) !important;
    color: var(--udea-green) !important;
    border-radius: 24px !important;
    padding: 8px 16px !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    transition: var(--transition) !important;
    white-space: normal !important;
    height: auto !important;
    min-height: 44px !important;
  }}
  div[data-testid="stHorizontalBlock"] .stButton > button[kind="secondary"]:hover {{
    background: var(--udea-green) !important;
    color: white !important;
    border-color: var(--udea-green) !important;
    transform: translateY(-2px) !important;
    box-shadow: var(--shadow-hover) !important;
  }}

  /* ── Card de respuesta principal ── */
  .udea-answer-card {{
    background: var(--udea-white);
    border-left: 4px solid var(--udea-green);
    border-radius: 0 var(--radius) var(--radius) 0;
    padding: 1.4rem 1.6rem;
    margin: 0.8rem 0;
    box-shadow: var(--shadow);
    transition: var(--transition);
    line-height: 1.7;
  }}
  .udea-answer-card:hover {{
    box-shadow: var(--shadow-hover);
  }}

  /* ── Badge de confianza ── */
  .udea-badge {{
    display: inline-flex;
    align-items: center;
    gap: 5px;
    border-radius: 20px;
    padding: 4px 12px;
    font-size: 0.80rem;
    font-weight: 700;
    letter-spacing: 0.3px;
    margin-right: 6px;
    margin-bottom: 4px;
  }}
  .udea-badge-green  {{ background: #E8F5E9; color: #1B5E20; border: 1px solid #A5D6A7; }}
  .udea-badge-yellow {{ background: #FFF8E1; color: #E65100; border: 1px solid #FFE082; }}
  .udea-badge-red    {{ background: #FFEBEE; color: #B71C1C; border: 1px solid #FFCDD2; }}
  .udea-badge-blue   {{ background: #E3F2FD; color: #0D47A1; border: 1px solid #BBDEFB; }}
  .udea-badge-gray   {{ background: #F5F5F5; color: #424242; border: 1px solid #E0E0E0; }}

  /* ── Sección de fuentes ── */
  .udea-source-item {{
    background: var(--udea-gray-lite);
    border-radius: 8px;
    padding: 8px 12px;
    margin: 4px 0;
    font-size: 0.83rem;
    border-left: 3px solid var(--udea-green-lite);
  }}

  /* ── Chat messages ── */
  [data-testid="stChatMessage"] {{
    border-radius: var(--radius) !important;
    margin-bottom: 0.5rem !important;
  }}

  /* ── Expander de auditoría ── */
  [data-testid="stExpander"] {{
    border: 1px solid #E0E0E0 !important;
    border-radius: var(--radius) !important;
    background: var(--udea-gray-lite) !important;
  }}
  [data-testid="stExpander"] summary {{
    font-size: 0.83rem !important;
    font-weight: 600 !important;
    color: var(--udea-gray-mid) !important;
  }}

  /* ── Métricas ── */
  [data-testid="metric-container"] {{
    background: var(--udea-white);
    border-radius: 10px;
    padding: 0.8rem !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
  }}

  /* ── Welcome banner ── */
  .udea-welcome-banner {{
    background: linear-gradient(135deg, var(--udea-green) 0%, var(--udea-green-lite) 100%);
    color: white;
    border-radius: var(--radius);
    padding: 1.6rem 2rem;
    margin-bottom: 1.4rem;
    box-shadow: var(--shadow-hover);
  }}
  .udea-welcome-banner h2 {{
    color: white !important;
    -webkit-text-fill-color: white !important;
    margin: 0 0 0.4rem 0 !important;
    font-size: 1.25rem !important;
  }}
  .udea-welcome-banner p {{
    color: rgba(255,255,255,0.9);
    margin: 0;
    font-size: 0.93rem;
    line-height: 1.5;
  }}
</style>
"""


def inject_udea_styles() -> None:
    """Inyecta los estilos CSS institucionales UdeA."""
    st.markdown(_UDEA_CSS, unsafe_allow_html=True)


def render_welcome_banner() -> None:
    """Muestra el banner de bienvenida con gradiente verde UdeA."""
    st.markdown(
        """
        <div class="udea-welcome-banner">
          <h2>🎓 ¡Hola! Soy tu Asesor Estudiantil Digital</h2>
          <p>
            Consulta reglamentos, procedimientos y normas académicas de la Universidad de Antioquia.<br>
            Obtén respuestas claras, con fuentes documentales verificables y en lenguaje sencillo.
          </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_suggested_questions(questions: list[str]) -> str | None:
    """
    Muestra pills de preguntas sugeridas.
    Retorna la pregunta clickeada o None si no se hizo clic.
    """
    st.markdown(
        "<p style='font-size:0.88rem;color:#616161;font-weight:600;margin-bottom:6px;'>"
        "💡 Preguntas frecuentes — haz clic para empezar:</p>",
        unsafe_allow_html=True,
    )
    cols = st.columns(len(questions))
    for col, question in zip(cols, questions):
        with col:
            if st.button(
                question,
                key=f"sug_q_{hash(question)}",
                use_container_width=True,
            ):
                return question
    return None


def _confidence_badge(confidence: float) -> str:
    """Genera HTML de badge de confianza con semáforo de color."""
    pct = int(confidence * 100)
    if confidence >= 0.70:
        cls, icon, label = "udea-badge-green", "🟢", f"Alta confianza ({pct}%)"
    elif confidence >= 0.45:
        cls, icon, label = "udea-badge-yellow", "🟡", f"Confianza media ({pct}%)"
    else:
        cls, icon, label = "udea-badge-red", "🔴", f"Confianza baja ({pct}%)"
    return f'<span class="udea-badge {cls}">{icon} {label}</span>'


def render_answer(answer: AnswerPayload) -> None:
    """
    Renderiza la respuesta en un card principal + expander de auditoría.
    Separa visualmente la lectura (respuesta) de los metadatos técnicos.
    """
    # ── 1. Respuesta principal en card institucional ───────────────────────
    st.markdown(
        f'<div class="udea-answer-card">{answer.answer}</div>',
        unsafe_allow_html=True,
    )

    # ── 2. Badges de estado (fuera del expander, visibles de inmediato) ────
    badges_html = _confidence_badge(answer.confidence)
    doc_count = len(answer.documents_used)
    badges_html += (
        f'<span class="udea-badge udea-badge-blue">📄 {doc_count} doc{"s" if doc_count != 1 else ""}</span>'
    )
    if answer.processing_time_ms > 0:
        t_s = answer.processing_time_ms / 1000
        badges_html += (
            f'<span class="udea-badge udea-badge-gray">⏱ {t_s:.1f} s</span>'
        )
    st.markdown(f'<div style="margin:10px 0 4px 0">{badges_html}</div>', unsafe_allow_html=True)

    # ── 3. Expander de auditoría con metadatos técnicos ───────────────────
    with st.expander("🔍 Auditoría — fuentes y metadatos técnicos", expanded=False):
        if answer.documents_used:
            st.markdown("**📚 Documentos consultados:**")
            for doc in answer.documents_used:
                st.markdown(f"- {doc}")

        if answer.sources:
            st.markdown("**📎 Fragmentos recuperados:**")
            for idx, source in enumerate(answer.sources, start=1):
                page_label = f"p. {source.page_number}" if source.page_number else "pág. no identificada"
                relevance_pct = int(source.score * 100)
                st.markdown(
                    f'<div class="udea-source-item">'
                    f'<strong>[{idx}]</strong> {source.source_name} — {page_label} '
                    f'<span style="color:#43A047;font-weight:700;">● {relevance_pct}% relevancia</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
                st.caption(source.text[:500] + ("…" if len(source.text) > 500 else ""))

        cols_meta = st.columns(3)
        cols_meta[0].metric("Confianza", f"{answer.confidence:.0%}")
        cols_meta[1].metric("Docs usados", doc_count)
        cols_meta[2].metric("Tiempo respuesta", f"{answer.processing_time_ms / 1000:.1f} s")

        if answer.intent:
            st.markdown(
                f"**Intención detectada:** `{answer.intent.category}` "
                f"| Confianza clasificador: `{answer.intent.confidence:.2f}`"
            )

        if answer.notes:
            st.info("📝 " + " | ".join(answer.notes))


def render_ingestion_summary(summary: IngestionSummary) -> None:
    """Muestra el resumen de la indexación con métricas estilizadas."""
    st.subheader("📊 Estado de indexación")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Archivos procesados", summary.files_processed)
    col2.metric("Chunks indexados", summary.chunks_indexed)
    col3.metric("Reutilizados", summary.reused_files)
    col4.metric("Errores", len(summary.errors))

    if summary.fallback_files:
        st.info(
            f"Se usó fallback con campo 'resuelve' en {summary.fallback_files} documento(s) "
            "cuando no se pudo extraer texto del PDF."
        )
    if summary.errors:
        st.warning("⚠️ " + "\n".join(summary.errors))
