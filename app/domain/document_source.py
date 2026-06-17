from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Protocol

from app.models import RetrievalHit


class DocumentSource(ABC):
    @abstractmethod
    def buscar(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        """Busca evidencia documental relevante para una consulta."""


class SupportsSearch(Protocol):
    def buscar(self, query: str, top_k: int = 5) -> list[RetrievalHit]:
        ...
