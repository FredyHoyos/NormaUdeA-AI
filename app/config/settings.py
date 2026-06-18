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
    strict_rag_only: bool = True
    strict_rag_min_score: float = 0.35
    strict_rag_min_hits: int = 1
    llm_provider: str = "auto"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-1.5-pro"
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_model_candidates: str = "llama3.1:8b,qwen2.5:7b,mistral:7b"
    ollama_timeout_seconds: int = 120
    temperature: float = 0.1
    bge_m3_model: str = "BAAI/bge-m3"
    bge_m3_local_dir: Path | None = None
    bge_m3_cache_dir: Path = Field(default=Path("data/models/.cache/huggingface"))
    reranker_enabled: bool = True
    reranker_model: str = "BAAI/bge-reranker-v2-m3"
    reranker_retrieval_k: int = 20
    reranker_final_k: int = 5
    reranker_use_llm_fallback: bool = True
    ocr_enabled: bool = True
    ocr_lang: str = "spa+eng"
    ocr_tesseract_cmd: str | None = None
    ocr_tessdata_prefix: str | None = None
    supabase_url: str | None = None
    supabase_service_role_key: str | None = None
    supabase_table_name: str = "normativas_udea"
    supabase_pdf_url_column: str = "url_pdf"
    supabase_select_columns: str = "id,numero,tipo_documento,asunto,fecha_expedicion,url_pdf,fecha_rastreo,resuelve"
    supabase_document_number_column: str = "numero"
    supabase_subject_column: str = "asunto"
    supabase_pdf_timeout_seconds: int = 120
    supabase_index_state_path: Path = Field(default=Path("data/ingestion/supabase_index_state.json"))
    supabase_use_resuelve_fallback: bool = True
    supabase_resuelve_max_chars: int = 1200
    streamlit_page_title: str = "Copiloto Administrativo Agéntico UdeA"
    streamlit_page_icon: str = "🎓"
    analytics_db_path: Path = Field(default=Path("data/analytics.db"))

    @property
    def supabase_table(self) -> str:
        return self.supabase_table_name

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    def ensure_directories(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.pdf_dir.mkdir(parents=True, exist_ok=True)
        self.chroma_dir.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.bge_m3_cache_dir.mkdir(parents=True, exist_ok=True)
        self.supabase_index_state_path.parent.mkdir(parents=True, exist_ok=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    settings = Settings()
    settings.ensure_directories()
    return settings
