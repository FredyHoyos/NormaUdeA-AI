# Arquitectura del MVP

El sistema sigue un flujo local-first para recuperar informacion desde PDFs almacenados en disco y exponerla mediante Streamlit.

## Capas

1. **Interfaz**: Streamlit recibe la pregunta del usuario y muestra respuesta, fuentes, confianza y documentos usados.
2. **Orquestacion**: `CrewAIManager` coordina clasificacion, recuperacion y redaccion.
3. **Agentes**:
   - `IntentClassifierAgent` identifica la intencion.
   - `RetrieverAgent` recupera evidencia desde ChromaDB.
   - `WriterAgent` redacta la respuesta final fundamentada.
4. **RAG local**:
   - `LocalPDFSource` indexa PDFs locales.
   - `PyMuPDF` extrae texto.
   - `BGEEmbeddings` genera embeddings.
   - `ChromaKnowledgeBase` persiste y consulta vectores.
5. **Extensibilidad**: `DocumentSource` abstrae el origen documental. `UdeaPortalSource` queda preparado para una version futura.

## Flujo

Usuario -> Streamlit -> CrewAI Manager -> Clasificador -> Recuperador -> ChromaDB -> Redactor -> UI

## Criterios del MVP

- Responder con lenguaje natural.
- Mostrar articulos y fragmentos encontrados.
- Exponer documentos usados.
- Mostrar confianza.
- No depender de scraping.
- Mantener ejecucion local sobre PDFs.
