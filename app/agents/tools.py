from __future__ import annotations

import logging
from typing import Any

from crewai.tools import BaseTool

from app.models import RetrievalHit
from app.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)


class DocumentSearchTool(BaseTool):
    name: str = "Buscar Documentos"
    description: str = "Busca fragmentos relevantes en la base documental universitaria utilizando la consulta del usuario. Devuelve pasajes de texto con fuente, pagina y puntuacion de relevancia."

    retriever: Retriever | None = None

    def _run(self, query: str, **kwargs: Any) -> str:
        if self.retriever is None:
            return "Error: recuperador de documentos no disponible."
        hits = self.retriever.retrieve(query)
        return self.retriever.build_context(hits)
