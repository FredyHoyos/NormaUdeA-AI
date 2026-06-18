from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class DocumentChunk(BaseModel):
    chunk_id: str
    text: str
    source_name: str
    source_path: str
    page_number: int | None = None
    chunk_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class RetrievalHit(BaseModel):
    chunk_id: str
    text: str
    score: float
    source_name: str
    source_path: str
    page_number: int | None = None
    chunk_index: int = 0
    metadata: dict[str, Any] = Field(default_factory=dict)


class QuestionIntent(BaseModel):
    category: str = "general"
    needs_retrieval: bool = True
    confidence: float = 0.0
    rationale: str = ""


class AnswerPayload(BaseModel):
    answer: str
    intent: QuestionIntent = Field(default_factory=QuestionIntent)
    confidence: float = 0.0
    documents_used: list[str] = Field(default_factory=list)
    sources: list[RetrievalHit] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
    processing_time_ms: float = 0.0


class IngestionSummary(BaseModel):
    files_processed: int = 0
    chunks_indexed: int = 0
    reused_files: int = 0
    fallback_files: int = 0
    errors: list[str] = Field(default_factory=list)


class IngestionProgress(BaseModel):
    stage: str
    message: str
    progress_percent: float = 0.0
    current_file: str | None = None
    total_files: int = 0
    files_processed: int = 0
    chunks_indexed: int = 0
