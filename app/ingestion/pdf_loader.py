from __future__ import annotations

import hashlib
import logging
from pathlib import Path

import fitz
import pytesseract
from PIL import Image

from app.config.settings import Settings
from app.ingestion.chunking import chunk_text
from app.models import DocumentChunk

logger = logging.getLogger(__name__)


def _stable_chunk_id(source_path: Path, page_number: int, chunk_index: int, text: str) -> str:
    digest = hashlib.sha1(f"{source_path}:{page_number}:{chunk_index}:{text}".encode("utf-8")).hexdigest()
    return digest[:24]


def _extract_page_text_with_ocr(page: fitz.Page, ocr_lang: str) -> str:
    # Render at higher DPI for better OCR quality on scanned PDFs.
    matrix = fitz.Matrix(2.0, 2.0)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    image = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
    return pytesseract.image_to_string(image, lang=ocr_lang).strip()


def extract_pdf_chunks(pdf_path: Path, settings: Settings) -> list[DocumentChunk]:
    chunks: list[DocumentChunk] = []
    document = fitz.open(pdf_path)
    ocr_unavailable = False

    if settings.ocr_tesseract_cmd:
        pytesseract.pytesseract.tesseract_cmd = settings.ocr_tesseract_cmd

    try:
        for page_index in range(len(document)):
            page = document[page_index]
            page_text = page.get_text("text").strip()
            if not page_text and settings.ocr_enabled and not ocr_unavailable:
                try:
                    page_text = _extract_page_text_with_ocr(page, settings.ocr_lang)
                except pytesseract.TesseractNotFoundError:
                    ocr_unavailable = True
                    logger.warning(
                        "Tesseract OCR no disponible. Instala Tesseract o desactiva OCR_ENABLED para omitir OCR."
                    )
                except Exception as exc:  # pragma: no cover - defensive logging
                    logger.warning("Fallo OCR en %s p.%s: %s", pdf_path.name, page_index + 1, exc)

            if not page_text:
                continue

            page_chunks = chunk_text(page_text, settings)
            if not page_chunks:
                continue

            for chunk_index, chunk in enumerate(page_chunks):
                chunks.append(
                    DocumentChunk(
                        chunk_id=_stable_chunk_id(pdf_path, page_index + 1, chunk_index, chunk),
                        text=chunk,
                        source_name=pdf_path.stem,
                        source_path=str(pdf_path),
                        page_number=page_index + 1,
                        chunk_index=chunk_index,
                        metadata={
                            "file_name": pdf_path.name,
                            "page_label": f"p. {page_index + 1}",
                        },
                    )
                )
    finally:
        document.close()

    logger.info("Extraidos %s chunks desde %s", len(chunks), pdf_path.name)
    return chunks
