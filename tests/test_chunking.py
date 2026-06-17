from app.config.settings import Settings
from app.ingestion.chunking import chunk_text


def test_chunk_text_splits_long_input() -> None:
    settings = Settings(chunk_size=10, chunk_overlap=2)
    text = " ".join(f"palabra{i}" for i in range(30))

    chunks = chunk_text(text, settings)

    assert len(chunks) >= 3
    assert all(chunks)
