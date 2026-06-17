# Bitacora de Presentacion - Copiloto Administrativo Agentico UdeA

## 1) Resumen ejecutivo
Copiloto Administrativo Agentico UdeA es un sistema de consulta academico-administrativa basado en RAG local sobre documentos PDF institucionales.
Permite hacer preguntas en lenguaje natural y responder con evidencia, fuentes y nivel de confianza.

Objetivo principal del MVP:
- Reducir tiempo de busqueda de normativas y procedimientos.
- Mejorar consistencia de respuestas.
- Aumentar trazabilidad con referencias documentales.

## 2) Problema que resuelve
Hoy, estudiantes y personal administrativo suelen enfrentar:
- Busqueda lenta entre multiples documentos PDF.
- Interpretaciones inconsistentes de la normativa.
- Dificultad para identificar la fuente exacta de una respuesta.
- Riesgo de desinformacion por respuestas no verificables.

## 3) Propuesta de valor
Valor funcional:
- Responde preguntas concretas con soporte documental.
- Muestra fuentes, documentos utilizados y confianza.
- Opera local-first (menor dependencia de servicios externos).

Valor para la institucion:
- Estandariza consultas recurrentes.
- Disminuye carga operativa en atencion de primer nivel.
- Facilita transparencia y auditoria de respuestas.

Valor para el usuario final:
- Menos tiempo buscando articulos y procedimientos.
- Respuestas mas claras y accionables.
- Mayor confianza por evidencia visible.

## 4) Publico objetivo
Primario:
- Estudiantes de pregrado y posgrado.
- Personal de atencion administrativa.

Secundario:
- Coordinaciones academicas.
- Decanaturas y unidades de apoyo.
- Monitores o mesas de ayuda institucionales.

## 5) Alcance del MVP
Incluye:
- Ingestion de PDFs locales.
- Indexacion semantica en base vectorial persistente.
- Clasificacion de intencion.
- Recuperacion de evidencia y redaccion de respuesta.
- Visualizacion en interfaz Streamlit.

No incluye aun:
- Conexion automatica a portales externos.
- Flujos de aprobacion humana en produccion.
- Gobierno documental avanzado (versionado normativo completo).

## 6) Herramientas y componentes
Frontend y experiencia:
- Streamlit.

Backend y orquestacion:
- Python.
- CrewAI Manager para coordinar agentes y flujo.

RAG y datos:
- ChromaDB para almacenamiento vectorial.
- Embeddings BGE-M3 (modo local configurable).
- PyMuPDF para extraccion de texto.
- OCR con pytesseract + Tesseract para PDFs escaneados.

LLM (flexible y portable):
- Auto-deteccion de proveedor: Ollama, OpenAI-compatible, Gemini o modo none.
- Soporte local para Ollama.
- Soporte OpenAI-compatible para LM Studio (por OPENAI_BASE_URL).

## 7) Arquitectura funcional (alto nivel)
Flujo de consulta:
1. Usuario pregunta en la UI.
2. Clasificador identifica intencion y necesidad de recuperacion.
3. Recuperador busca fragmentos relevantes en ChromaDB.
4. Redactor construye respuesta fundamentada.
5. UI muestra respuesta, fuentes, documentos y confianza.

Principio clave:
- Responder con evidencia explicita y no como caja negra.

## 8) Diferenciales del sistema
- Local-first: opera con documentos y componentes locales.
- Trazabilidad: muestra de donde sale cada respuesta.
- Portabilidad: configuracion por .env para distintos equipos.
- Flexibilidad de modelos: cambio de LLM sin modificar codigo.
- Contingencia: modo none para no romper el flujo cuando no hay proveedor.

## 9) Escalabilidad (tecnica y operativa)
Escalabilidad tecnica:
- Separacion por capas (UI, orquestacion, ingestion, retrieval, LLM).
- DocumentSource abstrae origen documental para agregar nuevas fuentes.
- Vectorstore persistente para crecer en volumen documental.
- Variables de entorno para cambiar proveedor LLM y parametros sin tocar codigo.

Escalabilidad funcional:
- Multi-facultad: separar colecciones por dependencia o normativa.
- Multi-corpus: reglamentos, resoluciones, circulares y manuales.
- Multi-canal: extender a API web o bot institucional.

Escalabilidad operativa:
- Flujo de indexacion periodica (batch).
- Validacion de cambios normativos y reindexacion.
- Gobierno de prompts y monitoreo de calidad de respuesta.

## 10) Viabilidad para pasar a produccion
Recomendaciones de hardening:
- Control de accesos y autenticacion.
- Auditoria de preguntas y respuestas (logs anonimizados).
- Cifrado de secretos y gestion de llaves.
- Politica de actualizacion de corpus documental.
- Monitoreo de latencia, errores y cobertura de respuestas.

## 11) Riesgos y mitigaciones
Riesgo: documentos desactualizados.
Mitigacion: pipeline de carga con fecha de vigencia y versionado.

Riesgo: respuestas ambiguas en consultas complejas.
Mitigacion: umbral de confianza + solicitud de aclaracion + fuentes visibles.

Riesgo: dependencia de un proveedor/modelo.
Mitigacion: estrategia multi-provider y modo local.

Riesgo: OCR de baja calidad en escaneos deficientes.
Mitigacion: preprocesamiento de imagen, revisiones y fallback manual.

## 12) KPIs para medir exito
Producto:
- Precision percibida de respuesta.
- Porcentaje de respuestas con fuente valida.
- Cobertura de preguntas frecuentes resueltas.

Operacion:
- Tiempo promedio de respuesta.
- Tasa de reintentos por baja confianza.
- Tiempo de indexacion por lote documental.

Impacto institucional:
- Reduccion de tickets repetitivos.
- Reduccion de tiempo de atencion por consulta.
- Satisfaccion de usuarios internos y estudiantes.

## 13) Plan de evolucion (roadmap)
Fase 1 (corto plazo):
- Consolidar corpus y criterios de calidad documental.
- Monitorear calidad de respuestas con preguntas de control.

Fase 2 (mediano plazo):
- Integrar nuevas fuentes institucionales.
- Exponer servicio via API para otros canales.
- Implementar evaluacion automatizada de respuestas.

Fase 3 (largo plazo):
- Analitica avanzada de consultas.
- Personalizacion por perfil de usuario.
- Flujos con aprobacion humana para casos criticos.

## 14) Guion sugerido para presentacion (5-7 minutos)
1. Contexto y dolor actual (45 s).
2. Que hace el sistema y para quien (45 s).
3. Demo corta con una pregunta real (2 min).
4. Mostrar fuentes, confianza y documentos usados (1 min).
5. Explicar arquitectura y escalabilidad (1 min).
6. Cerrar con impacto esperado y roadmap (45 s).

## 15) Guion de demo recomendado
Paso 1:
- Mostrar indexacion de PDFs locales.

Paso 2:
- Ejecutar 2 preguntas frecuentes del dominio.

Paso 3:
- Evidenciar referencias, pagina y score.

Paso 4:
- Cambiar modelo por .env (sin tocar codigo) para demostrar portabilidad.

Paso 5:
- Cerrar con metricas de impacto y siguientes pasos.

## 16) Mensaje de cierre para jurado/stakeholders
Este sistema convierte normativa dispersa en respuestas accionables, trazables y auditables.
El MVP ya demuestra valor operativo inmediato y una ruta clara para escalar a nivel institucional con bajo acoplamiento tecnologico.
