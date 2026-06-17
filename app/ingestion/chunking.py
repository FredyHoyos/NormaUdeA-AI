from __future__ import annotations

from app.config.settings import Settings


def chunk_text(text: str, settings: Settings) -> list[str]:
    words = text.split()
    if not words:
        return []

    chunk_size = max(100, settings.chunk_size)
    overlap = max(0, min(settings.chunk_overlap, chunk_size - 1))
    step = max(1, chunk_size - overlap)

    chunks: list[str] = []
    for start in range(0, len(words), step):
        end = min(len(words), start + chunk_size)
        chunk_words = words[start:end]
        chunk = " ".join(chunk_words).strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(words):
            break
    return chunks
