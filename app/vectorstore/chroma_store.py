from __future__ import annotations

import logging
import re

import chromadb

from app.config.settings import Settings
from app.embeddings.bge_m3 import BGEEmbeddings
from app.models import DocumentChunk, RetrievalHit

logger = logging.getLogger(__name__)


class ChromaKnowledgeBase:
    def __init__(self, settings: Settings, embeddings: BGEEmbeddings | None = None) -> None:
        self.settings = settings
        self.embeddings = embeddings or BGEEmbeddings(
            model_name=settings.bge_m3_model,
            local_model_dir=settings.bge_m3_local_dir,
            cache_folder=settings.bge_m3_cache_dir,
        )
        self.client = chromadb.PersistentClient(path=str(settings.chroma_dir))
        self.collection_name: str | None = None
        self.collection = None

    def _build_collection_name(self, embedding_dimension: int) -> str:
        # Separa colecciones por dimension real para evitar mezclar 384 y 1024.
        return f"{self.settings.chroma_collection}__dim_{embedding_dimension}"

    def _get_collection(self, embedding_dimension: int):
        self.collection_name = self._build_collection_name(embedding_dimension)
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        return self.collection

    def count(self) -> int:
        if self.collection is None:
            return 0
        return int(self.collection.count())

    def count_all(self) -> int:
        prefix = f"{self.settings.chroma_collection}__dim_"
        total = 0
        try:
            for collection in self.client.list_collections():
                if getattr(collection, "name", "").startswith(prefix):
                    total += int(collection.count())
        except Exception:
            return 0
        return total

    def _reset_collection(self, embedding_dimension: int) -> None:
        collection_name = self._build_collection_name(embedding_dimension)
        logger.warning(
            "Recreando coleccion de Chroma '%s' por incompatibilidad de embeddings",
            collection_name,
        )
        self.client.delete_collection(name=collection_name)
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        self.collection_name = collection_name

    @staticmethod
    def _is_dimension_mismatch_error(error: Exception) -> bool:
        message = str(error).lower()
        return "expecting embedding with dimension" in message and "got" in message

    def upsert_chunks(self, chunks: list[DocumentChunk]) -> int:
        if not chunks:
            return 0

        texts = [chunk.text for chunk in chunks]
        ids = [chunk.chunk_id for chunk in chunks]
        embeddings = self.embeddings.embed_documents(texts)
        embedding_dimension = len(embeddings[0])
        collection = self._get_collection(embedding_dimension)
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

        try:
            collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)
        except Exception as exc:
            if not self._is_dimension_mismatch_error(exc):
                raise

            # Si el modelo de embeddings cambio desde la ultima indexacion,
            # Chroma mantiene la dimension antigua en disco. Reiniciamos y reintentamos.
            self._reset_collection(embedding_dimension)
            self.collection.upsert(ids=ids, documents=texts, embeddings=embeddings, metadatas=metadatas)

        logger.info("Indexados %s chunks en ChromaDB", len(chunks))
        return len(chunks)

    def query(self, query: str, top_k: int | None = None) -> list[RetrievalHit]:
        limit = top_k or self.settings.retrieval_k
        query_embedding = self.embeddings.embed_query(query)
        embedding_dimension = len(query_embedding)
        collection = self._get_collection(embedding_dimension)
        if int(collection.count()) == 0:
            return []

        try:
            result = collection.query(query_embeddings=[query_embedding], n_results=limit)
        except Exception as exc:
            if self._is_dimension_mismatch_error(exc):
                logger.warning(
                    "Dimension mismatch al consultar '%s' (dim=%s). Se devuelve contexto vacio para evitar fallo.",
                    self.collection_name,
                    embedding_dimension,
                )
                return []
            raise

        semantic_hits: list[RetrievalHit] = []
        documents = result.get("documents", [[]])[0]
        metadatas = result.get("metadatas", [[]])[0]
        distances = result.get("distances", [[]])[0]
        ids = result.get("ids", [[]])[0]

        for chunk_id, text, metadata, distance in zip(ids, documents, metadatas, distances):
            similarity = max(0.0, 1.0 - float(distance or 0.0))
            semantic_hits.append(
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

        lexical_hits = self._query_article_lexical_hits(collection, query, limit=limit)
        return self._merge_hits(semantic_hits, lexical_hits, limit=limit)

    @staticmethod
    def _extract_article_number(query: str) -> int | None:
        match = re.search(r"\\bart[íi]?culo\\s+(\\d{1,4})\\b", query.lower())
        if not match:
            return None
        return int(match.group(1))

    def _query_article_lexical_hits(self, collection, query: str, limit: int) -> list[RetrievalHit]:
        article_number = self._extract_article_number(query)
        if article_number is None:
            return []

        # Add a direct textual match path for "Articulo N" questions.
        regex = rf"(?i)art[íi]?culo\\s+{article_number}\\b"
        try:
            result = collection.get(
                where_document={"$regex": regex},
                include=["documents", "metadatas"],
                limit=max(limit, 10),
            )
        except Exception as exc:
            logger.warning("Fallo busqueda lexical por articulo %s: %s", article_number, exc)
            return []

        ids = result.get("ids", []) or []
        documents = result.get("documents", []) or []
        metadatas = result.get("metadatas", []) or []

        hits: list[RetrievalHit] = []
        for rank, (chunk_id, text, metadata) in enumerate(zip(ids, documents, metadatas), start=1):
            # Strong lexical matches should rank near the top.
            lexical_score = max(0.80, 0.99 - (rank - 1) * 0.01)
            metadata_dict = dict(metadata or {})
            hits.append(
                RetrievalHit(
                    chunk_id=str(chunk_id),
                    text=str(text),
                    score=lexical_score,
                    source_name=str(metadata_dict.get("source_name", "desconocido")),
                    source_path=str(metadata_dict.get("source_path", "")),
                    page_number=int(metadata_dict.get("page_number") or 0) or None,
                    chunk_index=int(metadata_dict.get("chunk_index") or 0),
                    metadata=metadata_dict,
                )
            )
        return hits

    @staticmethod
    def _merge_hits(semantic_hits: list[RetrievalHit], lexical_hits: list[RetrievalHit], limit: int) -> list[RetrievalHit]:
        merged: dict[str, RetrievalHit] = {}

        for hit in semantic_hits:
            merged[hit.chunk_id] = hit

        for hit in lexical_hits:
            existing = merged.get(hit.chunk_id)
            if existing is None:
                merged[hit.chunk_id] = hit
                continue
            if hit.score > existing.score:
                merged[hit.chunk_id] = hit

        ordered = sorted(
            merged.values(),
            key=lambda item: (item.score, -(item.page_number or 10_000), -item.chunk_index),
            reverse=True,
        )
        return ordered[:limit]
