# Bitacora de Presentacion - Copiloto Administrativo Agentico UdeA

> **Última actualización:** Junio 2026 — Sprint MVP Hackathon  
> **Versión:** 2.0.0-mvp

---

## 1) Resumen ejecutivo

Copiloto Administrativo Agéntico UdeA es un sistema de consulta académico-administrativa basado en RAG local sobre documentos PDF institucionales. Permite hacer preguntas en lenguaje natural y responder con evidencia, fuentes y nivel de confianza.

**Objetivo principal del MVP:**
- Reducir tiempo de búsqueda de normativas y procedimientos.
- Traducir el lenguaje burocrático en respuestas claras y accionables.
- Aumentar trazabilidad con referencias documentales explícitas.
- Registrar analítica de interacciones para mejora continua.

---

## 2) Problema que resuelve

Hoy, estudiantes y personal administrativo suelen enfrentar:
- Búsqueda lenta entre múltiples documentos PDF.
- Interpretaciones inconsistentes de la normativa.
- Dificultad para identificar la fuente exacta de una respuesta.
- Riesgo de desinformación por respuestas no verificables.
- **Nuevo:** lenguaje burocrático inaccesible que desmotiva al estudiante a buscar información.

---

## 3) Propuesta de valor

**Valor funcional:**
- Responde preguntas concretas con soporte documental.
- **Traduce** la normativa densa a lenguaje coloquial y pasos accionables.
- Muestra fuentes exactas (artículo, reglamento, página) con cada respuesta.
- Muestra confianza, documentos utilizados y tiempo de procesamiento.
- Opera local-first (menor dependencia de servicios externos).

**Valor para la institución:**
- Estandariza consultas recurrentes.
- Disminuye carga operativa en atención de primer nivel.
- Facilita transparencia y auditoría de respuestas.
- Registro SQLite de todas las interacciones para análisis de patrones.

**Valor para el usuario final:**
- Menos tiempo buscando artículos y procedimientos.
- Respuestas más claras, empáticas y accionables.
- Mayor confianza por evidencia visible y citas explícitas.
- **Nuevo:** preguntas sugeridas en la pantalla inicial para superar el Cold Start.

---

## 4) Público objetivo

**Primario:**
- Estudiantes de pregrado y posgrado.
- Personal de atención administrativa.

**Secundario:**
- Coordinaciones académicas.
- Decanaturas y unidades de apoyo.
- Monitores o mesas de ayuda institucionales.

---

## 5) Alcance del MVP (versión 2.0)

**Incluye:**
- Ingesta de PDFs locales con OCR (Tesseract).
- Indexación semántica en base vectorial persistente (ChromaDB).
- Clasificación de intención (academic, administrative, regulation, procedures, general).
- Recuperación de evidencia con reranking.
- **[NUEVO]** Redacción empática: traducción de normativa a lenguaje natural con pasos accionables.
- **[NUEVO]** Trazabilidad explícita: cita de fuente obligatoria en cada afirmación normativa.
- **[NUEVO]** Cierre conversacional: pregunta de seguimiento en cursiva que anticipa el próximo paso.
- **[NUEVO]** Frontend institucional UdeA: paleta verde oficial, tipografía Inter, glassmorphism.
- **[NUEVO]** Preguntas sugeridas (Cold Start) con pills interactivos.
- **[NUEVO]** Registro de interacciones en SQLite: timestamp, intención, confianza, tiempo.
- **[NUEVO]** Sidebar con estadísticas de uso en tiempo real.
- **[NUEVO]** Docker Compose con volúmenes persistentes para todos los datos.
- Visualización de auditoría en Streamlit (expander con badges de color).

**No incluye aún:**
- Conexión automática a portales externos.
- Flujos de aprobación humana en producción.
- Gobierno documental avanzado (versionado normativo completo).

---

## 6) Herramientas y componentes

**Frontend y experiencia:**
- Streamlit con CSS institucional UdeA (Verde `#1B5E20`, blanco, gris oscuro).
- Google Fonts: Inter (300–700).
- Badges de semáforo: verde/amarillo/rojo para confianza.
- Expander de auditoría separado de la respuesta principal.

**Backend y orquestación:**
- Python 3.11+
- CrewAI Manager para coordinar agentes y flujo.
- SQLite (nativo) para registro analítico de interacciones.

**RAG y datos:**
- ChromaDB para almacenamiento vectorial persistente.
- Embeddings BGE-M3 (modo local configurable).
- PyMuPDF para extracción de texto.
- OCR con pytesseract + Tesseract para PDFs escaneados.

**LLM (flexible y portable):**
- Auto-detección de proveedor: Ollama, OpenAI-compatible, Gemini o modo `none`.
- Soporte local para Ollama.
- Soporte OpenAI-compatible para LM Studio (por `OPENAI_BASE_URL`).

**Infraestructura:**
- Docker Compose con volúmenes persistentes (`./data`, `./logs`).

---

## 7) Arquitectura funcional (alto nivel)

**Flujo de consulta:**
1. Usuario pregunta en la UI (o hace clic en pregunta sugerida → auto-disparo).
2. Clasificador identifica intención y necesidad de recuperación.
3. Recuperador busca fragmentos relevantes en ChromaDB.
4. Redactor (asesor empático) traduce la normativa a lenguaje natural.
5. UI muestra respuesta en card + badges de confianza + expander de auditoría.
6. Logger registra la interacción en SQLite (timestamp, intención, confianza, tiempo).

**Principio clave:**
- Responder con evidencia explícita, lenguaje empático y trazabilidad total.

---

## 8) Diferenciales del sistema

- **Local-first:** opera con documentos y componentes locales.
- **Trazabilidad:** cita exacta del artículo y documento en cada respuesta normativa.
- **Empatía:** asesor estudiantil, no un reglamento andante.
- **Portabilidad:** configuración por `.env` para distintos equipos.
- **Flexibilidad de modelos:** cambio de LLM sin modificar código.
- **Contingencia:** modo `none` para no romper el flujo cuando no hay proveedor.
- **Analítica:** registro SQLite de todas las interacciones para monitoreo.
- **Docker-ready:** volúmenes persistentes para datos y logs.

---

## 9) Escalabilidad (técnica y operativa)

**Escalabilidad técnica:**
- Separación por capas (UI, orquestación, ingesta, retrieval, LLM, analytics).
- `DocumentSource` abstrae origen documental para agregar nuevas fuentes.
- Vectorstore persistente para crecer en volumen documental.
- Variables de entorno para cambiar proveedor LLM y parámetros sin tocar código.
- `InteractionLogger` extensible (se puede migrar a PostgreSQL con un cambio mínimo).

**Escalabilidad funcional:**
- Multi-facultad: separar colecciones por dependencia o normativa.
- Multi-corpus: reglamentos, resoluciones, circulares y manuales.
- Multi-canal: extender a API web o bot institucional.

**Escalabilidad operativa:**
- Flujo de indexación periódica (batch).
- Validación de cambios normativos y reindexación.
- Dashboard analítico basado en SQLite ya disponible en sidebar.

---

## 10) Viabilidad para pasar a producción

**Recomendaciones de hardening:**
- Control de accesos y autenticación.
- Auditoría de preguntas y respuestas (logs anonimizados) — ya implementada en SQLite.
- Cifrado de secretos y gestión de llaves.
- Política de actualización de corpus documental.
- Monitoreo de latencia, errores y cobertura de respuestas — base ya disponible.

---

## 11) Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|-----------|
| Documentos desactualizados | Pipeline de carga con fecha de vigencia y versionado |
| Respuestas ambiguas | Umbral de confianza + cita de fuente obligatoria + pregunta de cierre |
| Dependencia de un proveedor/modelo | Estrategia multi-provider y modo local |
| OCR de baja calidad en escaneos | Preprocesamiento de imagen y fallback manual |
| **[NUEVO]** Respuestas "caja negra" | Trazabilidad innegociable: fuente citada en cada afirmación |
| **[NUEVO]** Cold Start (usuario paralizado) | Preguntas sugeridas con auto-disparo al hacer clic |

---

## 12) KPIs para medir éxito

**Producto:**
- Precisión percibida de respuesta.
- Porcentaje de respuestas con cita de fuente válida.
- Cobertura de preguntas frecuentes resueltas.
- **[NUEVO]** Tiempo promedio de respuesta (disponible en SQLite/sidebar).

**Operación:**
- Tiempo promedio de respuesta — ya medible desde el registro SQLite.
- Tasa de reintentos por baja confianza.
- Tiempo de indexación por lote documental.

**Impacto institucional:**
- Reducción de tickets repetitivos.
- Reducción de tiempo de atención por consulta.
- Satisfacción de usuarios internos y estudiantes.

---

## 13) Plan de evolución (roadmap)

**Fase 1 — Corto plazo (post hackathon):**
- Consolidar corpus y criterios de calidad documental.
- Monitorear calidad de respuestas con preguntas de control.
- Dashboard analítico visual basado en los datos SQLite.

**Fase 2 — Mediano plazo:**
- Integrar nuevas fuentes institucionales.
- Exponer servicio vía API para otros canales.
- Implementar evaluación automatizada de respuestas.
- Migrar SQLite a PostgreSQL para escala.

**Fase 3 — Largo plazo:**
- Analítica avanzada de consultas y patrones de uso.
- Personalización por perfil de usuario.
- Flujos con aprobación humana para casos críticos.
- Integración con portal estudiantil UdeA.

---

## 14) Guión sugerido para presentación (5-7 minutos)

1. **Contexto y dolor actual** (45 s): estudiantes perdidos entre PDFs de 200 páginas.
2. **Qué hace el sistema y para quién** (45 s): asesor empático que traduce reglamentos.
3. **Demo en vivo — Cold Start** (30 s): mostrar las 3 preguntas sugeridas, click y auto-disparo.
4. **Demo — Pregunta normativa** (90 s): mostrar respuesta empática + cita de fuente + pregunta de cierre.
5. **Mostrar fuentes, confianza y tiempo** (45 s): abrir el expander de auditoría, badges de color.
6. **Arquitectura y escalabilidad** (45 s): capas, Docker, SQLite, multi-provider.
7. **Cerrar con impacto esperado y roadmap** (45 s).

---

## 15) Guión de demo recomendado

**Paso 1 — Cold Start:**
- Mostrar pantalla inicial con banner verde UdeA + 3 pills de preguntas.
- Hacer clic en "¿Cómo solicito una cancelación de matrícula?" → respuesta auto-disparada.

**Paso 2 — Respuesta empática:**
- Verificar que la respuesta use pasos numerados/viñetas.
- Verificar cita explícita: "(Según el Artículo X del Reglamento Estudiantil...)".
- Verificar pregunta de cierre en cursiva al final.

**Paso 3 — Auditoría:**
- Abrir el expander "🔍 Auditoría — fuentes y metadatos técnicos".
- Mostrar badge de confianza (verde/amarillo/rojo), docs usados, tiempo de respuesta.
- Mostrar fragmentos recuperados con % de relevancia.

**Paso 4 — Analítica:**
- Mostrar sidebar con estadísticas de uso (consultas totales, confianza promedio).
- Mencionar que los datos persisten en `data/analytics.db` (SQLite).

**Paso 5 — Portabilidad:**
- Cambiar modelo por `.env` (sin tocar código) para demostrar flexibilidad.
- Mostrar `docker-compose.yml` con volúmenes para evidenciar persistencia.

---

## 16) Mensaje de cierre para jurado/stakeholders

Este sistema no es solo un chatbot que consulta PDFs.  
Es un **asesor estudiantil empático** que traduce el lenguaje burocrático universitario en respuestas claras, trazables y accionables.

El MVP ya demuestra:
- ✅ Valor operativo inmediato (respuestas con fuente verificable).
- ✅ Diseño empático orientado al usuario final (estudiante).
- ✅ Fundamentos técnicos sólidos para escalar (Docker, SQLite, multi-LLM).
- ✅ Analítica de interacciones lista para monitoreo y mejora continua.

Una ruta clara para escalar a nivel institucional con bajo acoplamiento tecnológico.

---

## 17) Cambios técnicos — Sprint MVP Hackathon (Junio 2026)

| # | Mejora | Archivos afectados |
|---|--------|-------------------|
| 1 | SQLite analytics logger | `app/analytics/interaction_logger.py`, `app/services/answer_service.py`, `app/config/settings.py`, `app/models.py` |
| 2 | Preguntas sugeridas (Cold Start) | `app/main.py`, `app/ui/components.py` |
| 3 | System Prompt empático (asesor estudiantil) | `app/agents/writer_agent.py` |
| 4 | Trazabilidad + cierre conversacional | `app/agents/writer_agent.py` |
| 5 | Frontend institucional UdeA | `app/ui/components.py`, `app/main.py` |
| + | Docker Compose con volúmenes persistentes | `docker-compose.yml` |
