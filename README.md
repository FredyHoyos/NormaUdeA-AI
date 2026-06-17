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
- `LLM_PROVIDER=none` para modo local de contingencia (sin llamadas a API)
- `OPENAI_API_KEY` o `GEMINI_API_KEY`
- `OPENAI_MODEL` o `GEMINI_MODEL`
- `PDF_DIR`, `CHROMA_DIR`, `CHUNK_SIZE`, `RETRIEVAL_K`
- `BGE_M3_MODEL=BAAI/bge-m3`
- `BGE_M3_LOCAL_DIR=data/models/bge-m3`
- `BGE_M3_CACHE_DIR=data/models/.cache/huggingface`

Modo estable de baja memoria (sin descarga de modelos):

- `BGE_M3_MODEL=local-hash-384`
- `OCR_ENABLED=true|false`
- `OCR_LANG=spa+eng`
- `OCR_TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe`

## OCR para PDFs escaneados

Si un PDF no tiene texto seleccionable, la ingesta intenta OCR pagina por pagina.

Requiere instalar Tesseract en el sistema operativo y tenerlo en `PATH`.

Si no esta en `PATH`, configura `OCR_TESSERACT_CMD` con la ruta completa del ejecutable.

- Windows: instala "Tesseract OCR" y reinicia la terminal.
- Si no deseas OCR, usa `OCR_ENABLED=false`.

## Modelo BGE-M3 portable

Para evitar depender de descargas en cada arranque, descarga el modelo una vez y reutilizalo localmente:

```bash
.venv\Scripts\python.exe scripts/download_bge_m3.py
```

Luego la app cargara el modelo desde `BGE_M3_LOCAL_DIR` si esa carpeta existe.

## Ejemplos de preguntas

Revisa `docs/test_questions.md`.

## Notas de diseño

- `DocumentSource` permite cambiar el origen documental sin tocar el resto del sistema.
- `LocalPDFSource` trabaja solo con PDFs locales.
- `UdeaPortalSource` existe solo como placeholder deshabilitado.
- No se implementa scraping ni descarga de documentos.

# NormaUdeA-AI
