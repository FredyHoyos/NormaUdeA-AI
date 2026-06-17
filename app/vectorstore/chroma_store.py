from __future__ import annotations

import logging
from pathlib import Path

import chromadb

from app.config.settings import Settings
from app.embeddings.bge_m3 import BGEEmbeddings
from app.models import DocumentChunk, RetrievalHit

logger = logging.getLogger(__name__)


class ChromaKnowledgeBase:
    def __init__(self, settings: Settings, embeddings: BGEEmbeddings | None = None) -> None:
        self.settings = settings
        self.embeddings = embeddings or BGEEmbeddings(settings.bge_m3_model)
        self.client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self.collection = self.client.get_or_create_collection(
            name=settings.chroma_collection,
            metadata={"hnsw:space": "cosine"},
        )

    def count(self) -> int:
        return int(self.collection.count())

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        if not chunks:
            return 0

        texts = [chunk.text for chunk in chunks]
        ids = [chunk.chunk_id for chunk in chunks]
        embeddings = self.embeddings.embed_documents(texts)
        metadatas = [
            {
                "source_name": chunk.source_name,
                "source_path": chunk.source_path,
                "page_number": chunk.page_number or 0,
                "chunk_index": chunk.chunk_index,
                **chunk.metadata,
            }
            for chunk in chunks
        ]

        self.collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        logger.info("Indexados %s chunks en ChromaDB", len(chunks))
        return len(chunks)

    def query(self, query: str, top_k: int | None = None) -> list[RetrievalHit]:
        if self.count() == 0:
            return []

        limit = top_k or self.settings.retrieval_k
        query_embedding = self.embeddings.embed_query(query)
        result = self.collection.query(query_embeddings=[query_embedding], n_results=limit)

        hits: list[RetrievalHit] = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        ids = result.get("ids", [[]])[0]

        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
            similarity = max(0.0, 1.0 - float(distance or 0.0))
            hits.append(
                RetrievalHit(
                    chunk_id=chunk_id,
                    text=text,
                    score=similarity,
                    source_name=str(metadata.get("source_name", "desconocido")),
                    source_path=str(metadata.get("source_path", "")),
                    page_number=int(metadata.get("page_number") or 0) or None,
                    chunk_index=int(metadata.get("chunk_index") or 0),
                    metadata=dict(metadata),
                )
            )
        return hits
