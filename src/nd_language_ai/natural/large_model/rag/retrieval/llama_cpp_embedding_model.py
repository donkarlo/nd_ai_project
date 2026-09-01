from pathlib import Path
from typing import List, Optional

import numpy as np

from nd_language_ai.natural.large_model.rag.retrieval.embedding_model import (
    EmbeddingModel,
    ProgressCallback,
)


class LlamaCppEmbeddingModel(EmbeddingModel):
    def __init__(self, model_path: Path, context_size: int, batch_size: int) -> None:
        self._model_path = Path(model_path)
        self._context_size = max(256, int(context_size))
        self._configured_batch_size = max(1, int(batch_size))
        self._effective_batch_size = self._configured_batch_size
        self._model: Optional[object] = None

    def _get_model(self):
        if self._model is None:
            if not self._model_path.exists():
                raise FileNotFoundError(f"Embedding model not found: {self._model_path}")
            from llama_cpp import Llama

            self._model = Llama(
                model_path=str(self._model_path),
                n_ctx=self._context_size,
                n_batch=self._context_size,
                n_ubatch=min(512, self._context_size),
                embedding=True,
                verbose=False,
            )
        return self._model

    def embed_one(self, text: str) -> np.ndarray:
        prepared_text = self._prepare_text(text, self._context_size - 8)
        result = self._get_model().create_embedding(prepared_text)
        vector = result["data"][0]["embedding"]
        return np.asarray(vector, dtype=np.float32)

    def embed_many(
        self,
        texts: List[str],
        progress_callback: ProgressCallback = None,
    ) -> np.ndarray:
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)

        vectors: List[np.ndarray] = []
        total = len(texts)
        current_index = 0

        while current_index < total:
            batch_size = min(self._effective_batch_size, total - current_index)
            batch = texts[current_index:current_index + batch_size]

            try:
                batch_vectors = self._embed_batch(batch)
            except TypeError:
                if batch_size == 1:
                    batch_vectors = [self.embed_one(batch[0])]
                else:
                    self._effective_batch_size = 1
                    continue
            except RuntimeError as error:
                if "llama_decode" not in str(error).lower() or batch_size == 1:
                    raise
                self._effective_batch_size = max(1, batch_size // 2)
                if progress_callback is not None:
                    progress_callback(
                        f"Embedding batch reduced to {self._effective_batch_size} for compatibility..."
                    )
                continue

            vectors.extend(batch_vectors)
            current_index += batch_size
            if progress_callback is not None:
                progress_callback(f"Embedding {current_index}/{total} candidates...")

        return np.vstack(vectors)

    def _embed_batch(self, texts: List[str]) -> List[np.ndarray]:
        if len(texts) == 1:
            return [self.embed_one(texts[0])]

        maximum_tokens_per_text = max(
            32,
            self._context_size // len(texts) - 8,
        )
        prepared_texts = [
            self._prepare_text(text, maximum_tokens_per_text)
            for text in texts
        ]
        result = self._get_model().create_embedding(prepared_texts)
        data = list(result["data"])
        data.sort(key=lambda item: int(item.get("index", 0)))
        if len(data) != len(texts):
            raise RuntimeError(
                f"Embedding model returned {len(data)} vectors for {len(texts)} texts."
            )
        return [
            np.asarray(item["embedding"], dtype=np.float32)
            for item in data
        ]

    def _prepare_text(self, text: str, maximum_token_count: int) -> str:
        if not text:
            return " "

        model = self._get_model()
        encoded_text = text.encode("utf-8")
        maximum_token_count = max(8, int(maximum_token_count))

        try:
            try:
                tokens = model.tokenize(
                    encoded_text,
                    add_bos=True,
                    special=False,
                )
            except TypeError:
                tokens = model.tokenize(encoded_text, add_bos=True)
        except Exception:
            return text[: max(32, maximum_token_count * 3)]

        if len(tokens) <= maximum_token_count:
            return text

        truncated_tokens = tokens[:maximum_token_count]
        try:
            truncated_text = model.detokenize(truncated_tokens).decode(
                "utf-8",
                errors="ignore",
            ).strip()
            if truncated_text:
                return truncated_text
        except Exception:
            pass

        character_ratio = maximum_token_count / max(1, len(tokens))
        character_count = max(32, int(len(text) * character_ratio))
        return text[:character_count]
