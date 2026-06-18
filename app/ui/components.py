"""Componentes UI institucionales UdeA para Streamlit.

Incluye:
- inject_udea_styles(): inyecta CSS con paleta oficial UdeA (inmune a dark/light mode).
- render_suggested_questions(): pills de preguntas frecuentes (cold start).
- render_answer(): card principal + expander de auditoría con badges.
- render_ingestion_summary(): métricas de indexación.
- render_sidebar_logo(): logo UdeA en sidebar.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

from app.models import AnswerPayload, IngestionSummary

# ── Paleta oficial UdeA (constantes hardcodeadas — no dependen del tema) ─────
_UDEA_GREEN      = "#1B5E20"
_UDEA_GREEN_MID  = "#2E7D32"
_UDEA_GREEN_LITE = "#43A047"
_UDEA_GREEN_BG   = "#E8F5E9"
_UDEA_WHITE      = "#FFFFFF"
_UDEA_GRAY_DARK  = "#1A1A1A"
_UDEA_GRAY_MID   = "#424242"
_UDEA_GRAY_LITE  = "#F5F5F5"
_UDEA_GRAY_BORDER= "#E0E0E0"
_UDEA_GOLD       = "#F9A825"
_UDEA_RED        = "#C62828"

# Ruta al logo (relativa a la raíz del proyecto)
_LOGO_PATH = Path(__file__).parent.parent.parent / "docs" / "logo_udea.png"


def _logo_base64() -> str:
    """Devuelve el logo UdeA codificado en base64 para embeber en HTML sin rutas."""
    try:
        data = _LOGO_PATH.read_bytes()
        return base64.b64encode(data).decode("utf-8")
    except Exception:
        return ""


# ── CSS institucional — 100% hardcoded, inmune a dark/light mode del OS ──────
_UDEA_CSS = """
<style>
  /* ── Google Fonts ── */
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

  /* ═══════════════════════════════════════════════════════════════════
     RESET GLOBAL — Forzamos tema claro con !important en TODO
     Esto anula cualquier inyección de dark mode del navegador o del OS
  ═══════════════════════════════════════════════════════════════════ */

  /* Fuerza color-scheme claro en el DOM raíz */
  :root {
    color-scheme: light only !important;
  }

  /* Fondo y texto base — nunca heredan del OS */
  html,
  body,
  [class*="css"],
  .stApp,
  .stApp > header,
  .main,
  .main .block-container {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif !important;
    background-color: #FFFFFF !important;
    color: #1A1A1A !important;
  }

  /* Contenedor principal */
  .main .block-container {
    padding-top: 1.5rem !important;
    max-width: 920px !important;
  }

  /* ── Título principal ── */
  h1 {
    background: linear-gradient(135deg, #1B5E20 0%, #43A047 100%) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    background-clip: text !important;
    font-weight: 700 !important;
    font-size: 1.85rem !important;
    letter-spacing: -0.5px !important;
    margin-bottom: 0.1rem !important;
  }

  /* ── Caption del título ── */
  .stCaption, [data-testid="stCaptionContainer"] p {
    color: #616161 !important;
    font-size: 0.88rem !important;
  }

  /* ═══════════════════════════════════════════════════════════════════
     SIDEBAR — Verde UdeA garantizado
  ═══════════════════════════════════════════════════════════════════ */
  [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1B5E20 0%, #2E7D32 100%) !important;
    border-right: none !important;
  }
  [data-testid="stSidebar"] > div:first-child {
    background: transparent !important;
  }
  /* Todos los textos en sidebar: blanco */
  [data-testid="stSidebar"],
  [data-testid="stSidebar"] p,
  [data-testid="stSidebar"] span,
  [data-testid="stSidebar"] label,
  [data-testid="stSidebar"] div,
  [data-testid="stSidebar"] strong,
  [data-testid="stSidebar"] small,
  [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
    color: #FFFFFF !important;
  }
  /* Métricas en sidebar */
  [data-testid="stSidebar"] [data-testid="stMetricValue"],
  [data-testid="stSidebar"] [data-testid="stMetricLabel"],
  [data-testid="stSidebar"] [data-testid="stMetricDelta"] {
    color: #FFFFFF !important;
  }
  /* Divider en sidebar */
  [data-testid="stSidebar"] hr {
    border-color: rgba(255,255,255,0.3) !important;
  }
  /* Caption en sidebar */
  [data-testid="stSidebar"] .stCaption,
  [data-testid="stSidebar"] [data-testid="stCaptionContainer"] p {
    color: rgba(255,255,255,0.75) !important;
  }
  /* Código inline en sidebar */
  [data-testid="stSidebar"] code {
    background: rgba(255,255,255,0.15) !important;
    color: #E8F5E9 !important;
    border-radius: 4px !important;
    padding: 1px 5px !important;
  }
  /* Botón primario en sidebar */
  [data-testid="stSidebar"] .stButton > button {
    background: rgba(255,255,255,0.15) !important;
    border: 1.5px solid rgba(255,255,255,0.55) !important;
    color: #FFFFFF !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 0.88rem !important;
    transition: background 0.22s, transform 0.15s !important;
    width: 100% !important;
  }
  [data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(255,255,255,0.28) !important;
    transform: translateY(-1px) !important;
  }
  /* Progress bar en sidebar */
  [data-testid="stSidebar"] [data-testid="stProgress"] > div > div {
    background-color: #A5D6A7 !important;
  }

  /* ═══════════════════════════════════════════════════════════════════
     ÁREA DE CHAT — Fondo y burbujas controladas
  ═══════════════════════════════════════════════════════════════════ */
  [data-testid="stChatMessage"] {
    background-color: #FAFAFA !important;
    border-radius: 12px !important;
    border: 1px solid #EEEEEE !important;
    margin-bottom: 0.6rem !important;
  }
  /* Texto dentro de los mensajes de chat */
  [data-testid="stChatMessage"] p,
  [data-testid="stChatMessage"] span,
  [data-testid="stChatMessage"] div {
    color: #1A1A1A !important;
  }
  /* Chat input */
  [data-testid="stChatInput"] {
    background-color: #FFFFFF !important;
    border: 1.5px solid #C8E6C9 !important;
    border-radius: 12px !important;
    color: #1A1A1A !important;
  }
  [data-testid="stChatInput"]:focus-within {
    border-color: #1B5E20 !important;
    box-shadow: 0 0 0 3px rgba(27,94,32,0.12) !important;
  }
  [data-testid="stChatInputTextArea"] {
    color: #1A1A1A !important;
  }

  /* ═══════════════════════════════════════════════════════════════════
     CARD DE RESPUESTA
  ═══════════════════════════════════════════════════════════════════ */
  .udea-answer-card {
    background: #FFFFFF !important;
    color: #1A1A1A !important;
    border-left: 4px solid #1B5E20;
    border-radius: 0 12px 12px 0;
    padding: 1.4rem 1.6rem;
    margin: 0.6rem 0;
    box-shadow: 0 4px 20px rgba(0,0,0,0.07);
    transition: box-shadow 0.22s;
    line-height: 1.75;
    font-size: 0.95rem;
  }
  .udea-answer-card:hover {
    box-shadow: 0 8px 32px rgba(27,94,32,0.14);
  }
  .udea-answer-card p, .udea-answer-card li, .udea-answer-card span {
    color: #1A1A1A !important;
  }
  .udea-answer-card strong { color: #1B5E20 !important; }
  .udea-answer-card em { color: #2E7D32 !important; }

  /* ═══════════════════════════════════════════════════════════════════
     BADGES DE CONFIANZA
  ═══════════════════════════════════════════════════════════════════ */
  .udea-badge {
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
  }
  .udea-badge-green  { background: #E8F5E9 !important; color: #1B5E20 !important; border: 1px solid #A5D6A7; }
  .udea-badge-yellow { background: #FFF8E1 !important; color: #BF360C !important; border: 1px solid #FFE082; }
  .udea-badge-red    { background: #FFEBEE !important; color: #B71C1C !important; border: 1px solid #FFCDD2; }
  .udea-badge-blue   { background: #E3F2FD !important; color: #0D47A1 !important; border: 1px solid #BBDEFB; }
  .udea-badge-gray   { background: #F5F5F5 !important; color: #424242 !important; border: 1px solid #E0E0E0; }

  /* ═══════════════════════════════════════════════════════════════════
     PILLS DE PREGUNTAS SUGERIDAS
  ═══════════════════════════════════════════════════════════════════ */
  /* Botones en columnas horizontales usados para pills */
  div[data-testid="column"] .stButton > button {
    background: #E8F5E9 !important;
    border: 1.5px solid #66BB6A !important;
    color: #1B5E20 !important;
    border-radius: 24px !important;
    padding: 8px 16px !important;
    font-size: 0.85rem !important;
    font-weight: 600 !important;
    transition: all 0.22s !important;
    white-space: normal !important;
    height: auto !important;
    min-height: 44px !important;
    line-height: 1.4 !important;
  }
  div[data-testid="column"] .stButton > button:hover {
    background: #1B5E20 !important;
    color: #FFFFFF !important;
    border-color: #1B5E20 !important;
    transform: translateY(-2px) !important;
    box-shadow: 0 6px 20px rgba(27,94,32,0.22) !important;
  }

  /* ═══════════════════════════════════════════════════════════════════
     FUENTES / SOURCE ITEMS
  ═══════════════════════════════════════════════════════════════════ */
  .udea-source-item {
    background: #F5F5F5 !important;
    color: #1A1A1A !important;
    border-radius: 8px;
    padding: 8px 12px;
    margin: 4px 0;
    font-size: 0.83rem;
    border-left: 3px solid #43A047;
  }

  /* ═══════════════════════════════════════════════════════════════════
     EXPANDER DE AUDITORÍA
  ═══════════════════════════════════════════════════════════════════ */
  [data-testid="stExpander"] {
    background: #FAFAFA !important;
    border: 1px solid #E0E0E0 !important;
    border-radius: 12px !important;
  }
  [data-testid="stExpander"] summary,
  [data-testid="stExpander"] details > summary {
    font-size: 0.83rem !important;
    font-weight: 600 !important;
    color: #424242 !important;
  }
  [data-testid="stExpander"] p,
  [data-testid="stExpander"] span,
  [data-testid="stExpander"] div {
    color: #1A1A1A !important;
  }

  /* ═══════════════════════════════════════════════════════════════════
     MÉTRICAS
  ═══════════════════════════════════════════════════════════════════ */
  [data-testid="metric-container"] {
    background: #FFFFFF !important;
    border: 1px solid #E8F5E9 !important;
    border-radius: 10px !important;
    padding: 0.8rem !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.05) !important;
  }
  [data-testid="stMetricValue"] {
    color: #1B5E20 !important;
    font-weight: 700 !important;
  }
  [data-testid="stMetricLabel"] {
    color: #424242 !important;
  }

  /* ═══════════════════════════════════════════════════════════════════
     ALERTS / INFO / WARNING
  ═══════════════════════════════════════════════════════════════════ */
  [data-testid="stInfo"] {
    background: #E3F2FD !important;
    color: #0D47A1 !important;
    border-left-color: #1565C0 !important;
  }
  [data-testid="stWarning"] {
    background: #FFF8E1 !important;
    color: #BF360C !important;
    border-left-color: #F57F17 !important;
  }

  /* ═══════════════════════════════════════════════════════════════════
     WELCOME BANNER
  ═══════════════════════════════════════════════════════════════════ */
  .udea-welcome-banner {
    background: linear-gradient(135deg, #1B5E20 0%, #43A047 100%) !important;
    color: #FFFFFF !important;
    border-radius: 14px;
    padding: 1.6rem 2rem;
    margin-bottom: 1.4rem;
    box-shadow: 0 8px 32px rgba(27,94,32,0.22);
  }
  .udea-welcome-banner h2 {
    color: #FFFFFF !important;
    -webkit-text-fill-color: #FFFFFF !important;
    margin: 0 0 0.5rem 0 !important;
    font-size: 1.25rem !important;
  }
  .udea-welcome-banner p {
    color: rgba(255,255,255,0.92) !important;
    margin: 0;
    font-size: 0.93rem;
    line-height: 1.55;
  }

  /* ── Texto helper de sugeridas ── */
  .udea-suggest-label {
    font-size: 0.88rem;
    color: #616161 !important;
    font-weight: 600;
    margin-bottom: 6px;
    display: block;
  }

  /* ═══════════════════════════════════════════════════════════════════
     HEADER LOGO ROW
  ═══════════════════════════════════════════════════════════════════ */
  .udea-header-row {
    display: flex;
    align-items: center;
    gap: 14px;
    margin-bottom: 0.4rem;
  }
  .udea-header-logo {
    height: 52px;
    width: auto;
    flex-shrink: 0;
    object-fit: contain;
  }
  .udea-header-text h1 {
    margin: 0 !important;
  }
</style>
"""


def inject_udea_styles() -> None:
    """Inyecta CSS institucional UdeA, forzando tema claro independientemente del OS."""
    st.markdown(_UDEA_CSS, unsafe_allow_html=True)


def render_header_with_logo() -> None:
    """Renderiza el encabezado principal con logo UdeA + título en línea."""
    logo_b64 = _logo_base64()
    if logo_b64:
        logo_img = (
            f'<img src="data:image/png;base64,{logo_b64}" '
            f'class="udea-header-logo" alt="Logo Universidad de Antioquia">'
        )
    else:
        logo_img = '<span style="font-size:2.4rem;">🎓</span>'

    st.markdown(
        f"""
        <div class="udea-header-row">
          {logo_img}
          <div class="udea-header-text">
            <h1>Copiloto Administrativo UdeA</h1>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Asesor estudiantil digital — Normas, reglamentos y procedimientos académicos · "
        "Universidad de Antioquia"
    )


def render_sidebar_logo() -> None:
    """Muestra el logo UdeA en la parte superior del sidebar."""
    logo_b64 = _logo_base64()
    if logo_b64:
        logo_html = (
            f'<img src="data:image/png;base64,{logo_b64}" '
            f'style="width:80px;height:auto;object-fit:contain;display:block;margin:0 auto 6px auto;" '
            f'alt="Universidad de Antioquia">'
        )
    else:
        logo_html = '<div style="font-size:3rem;text-align:center;">🎓</div>'

    st.markdown(
        f"""
        <div style="text-align:center;padding:1rem 0 0.5rem 0;">
          {logo_html}
          <strong style="font-size:1.05rem;color:#FFFFFF;display:block;margin-top:4px;">
            NormaUdeA-AI
          </strong>
          <span style="font-size:0.78rem;color:rgba(255,255,255,0.82);display:block;margin-top:2px;">
            Copiloto Administrativo Agéntico
          </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_welcome_banner() -> None:
    """Muestra el banner de bienvenida con gradiente verde UdeA."""
    st.markdown(
        """
        <div class="udea-welcome-banner">
          <h2>👋 ¡Hola! Soy tu Asesor Estudiantil Digital</h2>
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
        '<span class="udea-suggest-label">💡 Preguntas frecuentes — haz clic para empezar:</span>',
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

    # ── 2. Badges de estado ────────────────────────────────────────────────
    badges_html = _confidence_badge(answer.confidence)
    doc_count = len(answer.documents_used)
    badges_html += (
        f'<span class="udea-badge udea-badge-blue">📄 {doc_count} doc{"s" if doc_count != 1 else ""}</span>'
    )
    if answer.processing_time_ms > 0:
        t_s = answer.processing_time_ms / 1000
        badges_html += f'<span class="udea-badge udea-badge-gray">⏱ {t_s:.1f} s</span>'
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
                    f'<span style="color:#2E7D32;font-weight:700;">● {relevance_pct}% relevancia</span>'
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
