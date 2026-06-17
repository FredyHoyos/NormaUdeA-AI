from __future__ import annotations

import logging
import os
import re
from hashlib import sha1
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


_FALLBACK_MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
_HASH_PREFIX = "local-hash"


class BGEEmbeddings:
    def __init__(
        self,
        model_name: str = "BAAI/bge-m3",
        local_model_dir: str | Path | None = None,
        cache_folder: str | Path | None = None,
    ) -> None:
        self.model_name = model_name
        self.local_model_dir = Path(local_model_dir) if local_model_dir else None
        self.cache_folder = str(cache_folder) if cache_folder else None
        self.model = None

    def _is_hash_mode(self) -> bool:
        return self.model_name.lower().startswith(_HASH_PREFIX)

    def _hash_dimension(self) -> int:
        match = re.match(r"^local-hash-(\d+)$", self.model_name.strip().lower())
        if not match:
            return 384
        return max(32, int(match.group(1)))

    def _hash_embed(self, text: str, dimension: int) -> list[float]:
        vector = np.zeros(dimension, dtype=np.float32)
        tokens = [token for token in re.split(r"\W+", text.lower()) if token]
        if not tokens:
            return vector.tolist()

        for token in tokens:
            digest = sha1(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], byteorder="little", signed=False) % dimension
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign

        norm = float(np.linalg.norm(vector))
        if norm > 0.0:
            vector /= norm
        return vector.tolist()

    @staticmethod
    def _prepare_hf_runtime() -> None:
        # Evita rutas de descarga acelerada en Rust que en Windows pueden fallar por memoria.
        os.environ.setdefault("HF_HUB_ENABLE_HF_TRANSFER", "0")
        os.environ.setdefault("HF_HUB_DISABLE_XET", "1")
        os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    def _has_local_model_files(self) -> bool:
        if not self.local_model_dir or not self.local_model_dir.exists() or not self.local_model_dir.is_dir():
            return False
        required_markers = ("config.json", "modules.json")
        return any((self.local_model_dir / marker).exists() for marker in required_markers)

    def _get_model(self):
        if self.model is None:
            if self._is_hash_mode():
                logger.info("Usando embeddings locales por hashing (%s)", self.model_name)
                self.model = "hash"
                return self.model

            from sentence_transformers import SentenceTransformer

            self._prepare_hf_runtime()
            if self._has_local_model_files():
                logger.info("Cargando modelo de embeddings local desde %s", self.local_model_dir)
                self.model = SentenceTransformer(str(self.local_model_dir), cache_folder=self.cache_folder)
            else:
                if self.local_model_dir:
                    logger.warning(
                        "Carpeta local de embeddings no valida o incompleta en %s. Usando modelo remoto %s.",
                        self.local_model_dir,
                        self.model_name,
                    )
                logger.info("Cargando modelo de embeddings remoto %s", self.model_name)
                try:
                    self.model = SentenceTransformer(self.model_name, cache_folder=self.cache_folder)
                except Exception:
                    if self.model_name != _FALLBACK_MODEL_NAME:
                        logger.exception(
                            "Fallo cargando %s. Reintentando con fallback %s.",
                            self.model_name,
                            _FALLBACK_MODEL_NAME,
                        )
                        self.model = SentenceTransformer(_FALLBACK_MODEL_NAME, cache_folder=self.cache_folder)
                    else:
                        raise
        return self.model

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._is_hash_mode():
            dimension = self._hash_dimension()
            return [self._hash_embed(text, dimension) for text in texts]
        vectors = self._get_model().encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return vectors.tolist()

    def embed_query(self, text: str) -> list[float]:
        if self._is_hash_mode():
            return self._hash_embed(text, self._hash_dimension())
        vector = self._get_model().encode([text], normalize_embeddings=True, show_progress_bar=False)[0]
        return vector.tolist()
