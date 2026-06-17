from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Copiloto Administrativo Agéntico UdeA"
    data_dir: Path = Field(default=Path("data"))
    pdf_dir: Path = Field(default=Path("data/pdfs"))
    chroma_dir: Path = Field(default=Path("data/chroma"))
    logs_dir: Path = Field(default=Path("logs"))
    chroma_collection: str = "udea_documents"
    chunk_size: int = 900
    chunk_overlap: int = 180
    retrieval_k: int = 5
    max_context_chars: int = 12000
    confidence_threshold: float = 0.35
    llm_provider: str = "openai"
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-pro"
    temperature: float = 0.1
    bge_m3_model: str = "BAAI/bge-m3"
    streamlit_page_title: str = "Copiloto Administrativo Agéntico UdeA"
    streamlit_page_icon: str = "🎓"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
