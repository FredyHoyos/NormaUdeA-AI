# Copiloto Administrativo Agéntico UdeA

MVP funcional para una hackathon de 24 horas. Consulta PDFs locales con lenguaje natural, recupera evidencia semántica, redacta respuestas fundamentadas y muestra referencias exactas, documentos usados y nivel de confianza.

## Stack

- Streamlit
- Python
- CrewAI
- ChromaDB
- BGE-M3 embeddings
- PyMuPDF
- OpenAI o Gemini por configuracion en `.env`

## Estructura

- `app/` contiene la aplicacion principal.
- `data/pdfs/` almacena los PDFs locales.
- `data/chroma/` guarda la base vectorial persistente.
- `docs/` contiene arquitectura, diagrama y preguntas de prueba.

## Flujo

1. El usuario escribe una pregunta.
2. El agente clasificador detecta la intencion.
3. El agente recuperador consulta ChromaDB.
4. El agente redactor genera una respuesta con evidencia.
5. Streamlit muestra respuesta, fuentes, documentos y confianza.

## Instalacion

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Ejecucion

1. Coloca los PDFs locales en `data/pdfs/`.
2. Inicia la app:

```bash
streamlit run app/main.py
```

3. Presiona `Indexar PDFs locales` desde la barra lateral.
4. Haz una pregunta en lenguaje natural.

## Variables de entorno

- `LLM_PROVIDER=openai|gemini`
- `OPENAI_API_KEY` o `GEMINI_API_KEY`
- `OPENAI_MODEL` o `GEMINI_MODEL`
- `PDF_DIR`, `CHROMA_DIR`, `CHUNK_SIZE`, `RETRIEVAL_K`

## Ejemplos de preguntas

Revisa `docs/test_questions.md`.

## Notas de diseño

- `DocumentSource` permite cambiar el origen documental sin tocar el resto del sistema.
- `LocalPDFSource` trabaja solo con PDFs locales.
- `UdeaPortalSource` existe solo como placeholder deshabilitado.
- No se implementa scraping ni descarga de documentos.

# NormaUdeA-AI
