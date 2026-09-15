"""Provider-neutral embedding contracts and the local BGE-M3 adapter."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol


class Embedder(Protocol):
    model_version: str
    dimension: int

    async def embed(self, texts: Sequence[str]) -> list[list[float]]: ...


EMBEDDING_MODEL = "BAAI/bge-m3"
EMBEDDING_MODEL_REVISION = (
    "5617a9f61b028005a4858fdac845db406aefb181"  # pragma: allowlist secret
)
EMBEDDING_MODEL_VERSION = f"{EMBEDDING_MODEL}@{EMBEDDING_MODEL_REVISION}"
EMBEDDING_DIMENSION = 1024


class BgeM3Embedder:
    """Lazy local BGE-M3 adapter, suitable for Kaggle or a GPU worker."""

    model_version = EMBEDDING_MODEL_VERSION
    dimension = EMBEDDING_DIMENSION

    def __init__(
        self,
        model_name: str = EMBEDDING_MODEL,
        *,
        revision: str | None = EMBEDDING_MODEL_REVISION,
        device: str | None = None,
    ) -> None:
        self.model_version = f"{model_name}@{revision}" if revision else model_name
        self._model_name = model_name
        self._revision = revision
        self._device = device
        self._model = None

    def _load(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "BGE-M3 requires sentence-transformers; install it in the embedding environment"
                ) from exc
            kwargs = {"device": self._device} if self._device else {}
            if self._revision:
                kwargs["revision"] = self._revision
            self._model = SentenceTransformer(self._model_name, **kwargs)
        return self._model

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        vectors = self._load().encode(
            list(texts), normalize_embeddings=True, convert_to_numpy=True, show_progress_bar=False
        )
        result = vectors.tolist()
        if any(len(vector) != self.dimension for vector in result):
            raise ValueError(f"Expected {self.dimension}-dimension BGE-M3 vectors")
        return result
