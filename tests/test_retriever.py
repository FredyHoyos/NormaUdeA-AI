from app.config.settings import Settings
from app.models import RetrievalHit
from app.retrieval.retriever import Retriever


class _FakeSource:
    def buscar(self, query: str, top_k: int = 5):
        _ = query
        _ = top_k
        return [
            RetrievalHit(
                chunk_id="a",
                text="ARTICULO 178. Texto no relevante para la consulta.",
                score=0.91,
                source_name="1_REGLAMENTO_ESTUDIANTIL_DE_PREGRADO",
                source_path="https://example.com/a.pdf",
                page_number=10,
                chunk_index=0,
                metadata={"db_asunto": "Reglamento estudiantil de pregrado"},
            ),
            RetrievalHit(
                chunk_id="b",
                text="ARTÍCULO 78. Derechos y deberes del estudiante...",
                score=0.62,
                source_name="1_REGLAMENTO_ESTUDIANTIL_DE_PREGRADO",
                source_path="https://example.com/a.pdf",
                page_number=11,
                chunk_index=0,
                metadata={"db_asunto": "Reglamento estudiantil de pregrado"},
            ),
            RetrievalHit(
                chunk_id="c",
                text="ARTÍCULO 78. Texto de otro reglamento no de pregrado.",
                score=0.88,
                source_name="Reglamento_Posgrado",
                source_path="https://example.com/b.pdf",
                page_number=8,
                chunk_index=0,
                metadata={"db_asunto": "Reglamento estudiantil de posgrado"},
            ),
        ]


class _FakeSourceNoExact:
    def buscar(self, query: str, top_k: int = 5):
        _ = query
        _ = top_k
        return [
            RetrievalHit(
                chunk_id="x",
                text="ARTÍCULO 12. ...",
                score=0.85,
                source_name="Reglamento_Posgrado",
                source_path="https://example.com/x.pdf",
                page_number=4,
                chunk_index=0,
                metadata={"db_asunto": "Reglamento de posgrado"},
            ),
            RetrievalHit(
                chunk_id="y",
                text="ARTÍCULO 34. ...",
                score=0.60,
                source_name="1_REGLAMENTO_ESTUDIANTIL_DE_PREGRADO",
                source_path="https://example.com/y.pdf",
                page_number=5,
                chunk_index=0,
                metadata={"db_asunto": "Reglamento estudiantil de pregrado"},
            ),
        ]


def test_prioritizes_exact_article_number_over_higher_similarity() -> None:
    retriever = Retriever(document_source=_FakeSource(), settings=Settings(reranker_enabled=False))

    hits = retriever.retrieve("que dice el articulo 78 de pregrado", top_k=3)

    assert hits[0].chunk_id == "b"


def test_prioritizes_pregrado_context_when_no_exact_article_match() -> None:
    retriever = Retriever(document_source=_FakeSourceNoExact(), settings=Settings(reranker_enabled=False))

    hits = retriever.retrieve("que dice el articulo 78 de pregrado", top_k=2)

    assert hits[0].chunk_id == "y"
