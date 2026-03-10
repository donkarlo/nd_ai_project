from typing import List
import numpy as np
from llama_cpp import Llama


class Embedder:
    def __init__(self, model_path: str, n_ctx: int, batch_size: int):
        self._model_path = str(model_path)
        self._n_ctx = int(n_ctx)
        self._batch_size = int(batch_size)

        self._llm = Llama(
            model_path=self._model_path,
            n_ctx=self._n_ctx,
            embedding=True,
            verbose=False
        )

    def embed_one(self, text: str) -> np.ndarray:
        result = self._llm.create_embedding(text)
        vector = result["data"][0]["embedding"]
        return np.asarray(vector, dtype=np.float32)

    def embed_many(self, texts: List[str]) -> np.ndarray:
        vectors: List[np.ndarray] = []
        index = 0
        while index < len(texts):
            batch = texts[index:index + self._batch_size]
            for t in batch:
                vectors.append(self.embed_one(t))
            index += self._batch_size

        if not vectors:
            return np.zeros((0, 0), dtype=np.float32)

        return np.vstack(vectors)
