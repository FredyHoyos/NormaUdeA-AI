from __future__ import annotations

import hashlib
import logging
import os
import shutil
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from app.config.settings import Settings
from app.ingestion.chunking import chunk_text
from app.models import DocumentChunk

logger = logging.getLogger(__name__)
_OCR_UNAVAILABLE_REPORTED = False
_OCR_LANGUAGE_FALLBACK_REPORTED = False


def _stable_chunk_id(source_path: Path, page_number: int, chunk_index: int, text: str) -> str:
    digest = hashlib.sha1(f"{source_path}:{page_number}:{chunk_index}:{text}".encode("utf-8")).hexdigest()
    return digest[:24]


def _extract_page_text_with_ocr(page: fitz.Page, ocr_lang: str) -> str:
    # Render at higher DPI for better OCR quality on scanned PDFs.
    matrix = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return pytesseract.image_to_string(image, lang=ocr_lang).strip()


def resolve_tesseract_command(settings: Settings) -> str | None:
    if not settings.ocr_enabled:
        return None

    configured = (settings.ocr_tesseract_cmd or "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.exists():
            return str(configured_path)
        detected = shutil.which(configured)
        if detected:
            return detected

    detected_default = shutil.which("tesseract")
    if detected_default:
        return detected_default

    return None


def resolve_tessdata_prefix(settings: Settings) -> str | None:
    configured = (settings.ocr_tessdata_prefix or "").strip()
    if configured:
        configured_path = Path(configured)
        if configured_path.exists() and configured_path.is_dir():
            return str(configured_path)

    cmd = resolve_tesseract_command(settings)
    if not cmd:
        return None
    inferred = Path(cmd).parent / "tessdata"
    if inferred.exists() and inferred.is_dir():
        return str(inferred)
    return None


def is_ocr_runtime_available(settings: Settings) -> bool:
    return resolve_tesseract_command(settings) is not None


def _resolve_ocr_language(settings: Settings) -> str | None:
    global _OCR_LANGUAGE_FALLBACK_REPORTED

    requested = [token.strip() for token in str(settings.ocr_lang or "").split("+") if token.strip()]
    if not requested:
        requested = ["eng"]

    try:
        installed = {lang.strip() for lang in pytesseract.get_languages(config="") if lang.strip()}
    except Exception:
        installed = set()

    if not installed:
        # Si no se puede consultar la lista, usar la configuración declarada.
        return "+".join(requested)

    available_requested = [lang for lang in requested if lang in installed]
    if available_requested:
        return "+".join(available_requested)

    # Fallback útil para no bloquear OCR cuando falta spa.traineddata.
    for fallback_lang in ("eng", "spa"):
        if fallback_lang in installed:
            if not _OCR_LANGUAGE_FALLBACK_REPORTED:
                logger.warning(
                    "Idiomas OCR solicitados no disponibles (%s). Usando fallback '%s'.",
                    "+".join(requested),
                    fallback_lang,
                )
                _OCR_LANGUAGE_FALLBACK_REPORTED = True
            return fallback_lang

    any_lang = sorted(installed)[0]
    if not _OCR_LANGUAGE_FALLBACK_REPORTED:
        logger.warning(
            "Idiomas OCR solicitados no disponibles (%s). Usando idioma instalado '%s'.",
            "+".join(requested),
            any_lang,
        )
        _OCR_LANGUAGE_FALLBACK_REPORTED = True
    return any_lang


def _extract_chunks_from_document(
    document: fitz.Document,
    source_name: str,
    source_path: str,
    settings: Settings,
) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    ocr_unavailable = False
    tesseract_cmd = resolve_tesseract_command(settings)
    effective_ocr_lang: str | None = None

    if tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        tessdata_prefix = resolve_tessdata_prefix(settings)
        if tessdata_prefix:
            os.environ["TESSDATA_PREFIX"] = tessdata_prefix
        effective_ocr_lang = _resolve_ocr_language(settings)
    elif settings.ocr_enabled:
        global _OCR_UNAVAILABLE_REPORTED
        if not _OCR_UNAVAILABLE_REPORTED:
            logger.warning(
                "Tesseract OCR no disponible en PATH ni en OCR_TESSERACT_CMD. "
                "Instalalo y reinicia para procesar PDFs escaneados."
            )
            _OCR_UNAVAILABLE_REPORTED = True

    for page_index in range(len(document)):
        page = document[page_index]
        page_text = page.get_text("text").strip()
        if (
            not page_text
            and settings.ocr_enabled
            and not ocr_unavailable
            and tesseract_cmd
            and effective_ocr_lang
        ):
            try:
                page_text = _extract_page_text_with_ocr(page, effective_ocr_lang)
            except pytesseract.TesseractNotFoundError:
                ocr_unavailable = True
                logger.warning(
                    "Tesseract OCR no disponible. Instala Tesseract o desactiva OCR_ENABLED para omitir OCR."
                )
            except pytesseract.TesseractError as exc:
                # Evita repetir el mismo error por cada página cuando falla el idioma.
                ocr_unavailable = True
                logger.warning("OCR deshabilitado para %s por error de idioma/configuración: %s", source_name, exc)
            except Exception as exc:  # pragma: no cover - defensive logging
                logger.warning("Fallo OCR en %s p.%s: %s", source_name, page_index + 1, exc)

        if not page_text:
            continue

        page_chunks = chunk_text(page_text, settings)
        if not page_chunks:
            continue

        for chunk_index, chunk in enumerate(page_chunks):
            chunks.append(
                DocumentChunk(
                    chunk_id=_stable_chunk_id(Path(source_path), page_index + 1, chunk_index, chunk),
                    text=chunk,
                    source_name=source_name,
                    source_path=source_path,
                    page_number=page_index + 1,
                    chunk_index=chunk_index,
                    metadata={
                        "file_name": f"{source_name}.pdf",
                        "page_label": f"p. {page_index + 1}",
                    },
                )
            )

    return chunks


def extract_pdf_chunks(pdf_path: Path, settings: Settings) -> list[DocumentChunk]:
    document = fitz.open(pdf_path)
    try:
        chunks = _extract_chunks_from_document(
            document=document,
            source_name=pdf_path.stem,
            source_path=str(pdf_path),
            settings=settings,
        )
    finally:
        document.close()

    logger.info("Extraidos %s chunks desde %s", len(chunks), pdf_path.name)
    return chunks


def extract_pdf_chunks_from_bytes(pdf_content: bytes, source_name: str, source_path: str, settings: Settings) -> list[DocumentChunk]:
    document = fitz.open(stream=pdf_content, filetype="pdf")
    try:
        chunks = _extract_chunks_from_document(
            document=document,
            source_name=source_name,
            source_path=source_path,
            settings=settings,
        )
    finally:
        document.close()

    logger.info("Extraidos %s chunks desde recurso remoto %s", len(chunks), source_name)
    return chunks
