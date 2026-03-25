from pathlib import Path
from typing import List, Tuple
import json
import numpy as np
import faiss

from nd_ai.knoweldge_representation.language.natural.large_model.rag.embedder import Embedder


class Index:
    def __init__(self, embedder: Embedder, cache_dir: Path):
        self._embedder = embedder
        self._cache_dir = cache_dir
        self._faiss_index = None
        self._chunks: List[dict] = []

    def has_cache(self, index_path: Path, chunks_path: Path) -> bool:
        return index_path.exists() and chunks_path.exists()

    def save(self, index_path: Path, chunks_path: Path) -> None:
        if self._faiss_index is None:
            raise RuntimeError("FAISS index is not built")

        self._cache_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self._faiss_index, str(index_path))

        with chunks_path.open("w", encoding="utf-8") as file:
            for ch in self._chunks:
                file.write(json.dumps(ch, ensure_ascii=False) + "\n")

    def load(self, index_path: Path, chunks_path: Path) -> None:
        self._faiss_index = faiss.read_index(str(index_path))
        self._chunks = []

        with chunks_path.open("r", encoding="utf-8") as file:
            for line in file:
                line = line.strip()
                if not line:
                    continue
                self._chunks.append(json.loads(line))

    def build(self, chunks: List[dict]) -> None:
        self._chunks = chunks

        texts = [c["tex"] for c in self._chunks]
        vectors = self._embedder.embed_many(texts)

        if vectors.size == 0:
            raise RuntimeError("No vectors created")

        faiss.normalize_L2(vectors)
        dimension = int(vectors.shape[1])
        self._faiss_index = faiss.IndexFlatIP(dimension)
        self._faiss_index.add(vectors)

    def search(self, query: str, top_k: int) -> List[Tuple[float, dict]]:
        if self._faiss_index is None:
            return []

        query_vector = self._embedder.embed_one(query).astype(np.float32).reshape(1, -1)
        faiss.normalize_L2(query_vector)

        distances, indices = self._faiss_index.search(query_vector, int(top_k))
        hits: List[Tuple[float, dict]] = []
        for score, idx in zip(distances[0].tolist(), indices[0].tolist()):
            if idx < 0 or idx >= len(self._chunks):
                continue
            hits.append((float(score), self._chunks[idx]))

        if hits:
            return hits

        return self._search_lexical(query, top_k)

    def _search_lexical(self, query: str, top_k: int) -> List[Tuple[float, dict]]:
        query_tokens = [t for t in query.lower().replace("?", " ").replace(",", " ").split() if t]
        if not query_tokens:
            return []

        scored: List[Tuple[float, dict]] = []
        for ch in self._chunks:
            hay = (ch.get("tex", "") + " " + ch.get("source_path", "")).lower()
            hits = 0
            for t in query_tokens:
                if t in hay:
                    hits += 1
            if hits > 0:
                score = float(hits) / float(len(query_tokens))
                scored.append((score, ch))

        scored.sort(key=lambda x: x[0], reverse=True)
        return scored[: int(top_k)]
