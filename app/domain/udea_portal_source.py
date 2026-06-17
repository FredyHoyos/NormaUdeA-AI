from __future__ import annotations

from app.domain.document_source import DocumentSource
from app.models import RetrievalHit


class UdeaPortalSource(DocumentSource):
    """Implementacion reservada para futuras versiones."""

    def buscar(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        raise NotImplementedError("Implementacion reservada para futuras versiones")
