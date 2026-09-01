import hashlib
from collections import OrderedDict
from pathlib import Path
from typing import List

import numpy as np

from nd_language_ai.natural.large_model.rag.retrieval.embedding_model import (
    ProgressCallback,
)
from nd_language_ai.natural.large_model.rag.retrieval.llama_cpp_embedding_model import (
    LlamaCppEmbeddingModel,
)


class CachedLlamaCppEmbeddingModel(LlamaCppEmbeddingModel):
    _SINGLE_CACHE_LIMIT = 256
    _BATCH_CACHE_LIMIT = 128

    def __init__(
        self,
        model_path: Path,
        context_size: int,
        batch_size: int,
    ) -> None:
        super().__init__(model_path, context_size, batch_size)
        self._single_cache: OrderedDict[str, np.ndarray] = OrderedDict()
        self._batch_cache: OrderedDict[str, np.ndarray] = OrderedDict()

    def embed_one(self, text: str) -> np.ndarray:
        cache_key = self._text_key(text)
        cached = self._single_cache.get(cache_key)
        if cached is not None:
            self._single_cache.move_to_end(cache_key)
            return cached.copy()

        vector = super().embed_one(text).astype(np.float32, copy=False)
        self._remember_single(cache_key, vector)
        return vector

    def embed_many(
        self,
        texts: List[str],
        progress_callback: ProgressCallback = None,
    ) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)

        cache_key = self._batch_key(texts)
        cached = self._batch_cache.get(cache_key)
        if cached is not None:
            self._batch_cache.move_to_end(cache_key)
            if progress_callback is not None:
                progress_callback(
                    f"Embedding RAM cache hit: reused {len(texts)} candidate vectors."
                )
            return cached.copy()

        vectors = super().embed_many(texts, progress_callback).astype(
            np.float32,
            copy=False,
        )
        self._remember_batch(cache_key, vectors)
        return vectors

    def clear_embedding_cache(self) -> None:
        self._single_cache.clear()
        self._batch_cache.clear()

    def _remember_single(
        self,
        cache_key: str,
        vector: np.ndarray,
    ) -> None:
        self._single_cache[cache_key] = vector.copy()
        self._single_cache.move_to_end(cache_key)
        while len(self._single_cache) > self._SINGLE_CACHE_LIMIT:
            self._single_cache.popitem(last=False)

    def _remember_batch(
        self,
        cache_key: str,
        vectors: np.ndarray,
    ) -> None:
        self._batch_cache[cache_key] = vectors.copy()
        self._batch_cache.move_to_end(cache_key)
        while len(self._batch_cache) > self._BATCH_CACHE_LIMIT:
            self._batch_cache.popitem(last=False)

    def _text_key(self, text: str) -> str:
        digest = hashlib.sha256()
        digest.update(text.encode("utf-8", errors="surrogatepass"))
        return digest.hexdigest()

    def _batch_key(self, texts: List[str]) -> str:
        digest = hashlib.sha256()
        digest.update(str(self._effective_batch_size).encode("ascii"))
        digest.update(b"\0")
        for text in texts:
            encoded = text.encode("utf-8", errors="surrogatepass")
            digest.update(len(encoded).to_bytes(8, "little", signed=False))
            digest.update(encoded)
        return digest.hexdigest()
