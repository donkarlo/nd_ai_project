import time
from collections import OrderedDict
from typing import Dict, List, Tuple

import numpy as np

from nd_language_ai.natural.large_model.rag.retrieval.embedding_model import (
    ProgressCallback,
)
from nd_language_ai.natural.large_model.rag.retrieval.persistent_hybrid_index import (
    PersistentHybridIndex,
)


class TimedPersistentHybridIndex(PersistentHybridIndex):
    _RETRIEVAL_CACHE_LIMIT = 64

    def __init__(self, *args, **kwargs) -> None:
        self._retrieval_cache: OrderedDict[
            Tuple[str, int],
            Tuple[Tuple[float, str, str], ...],
        ] = OrderedDict()
        self._last_search_timings: Dict[str, float] = {}
        super().__init__(*args, **kwargs)

    def search(
        self,
        question: str,
        top_k: int,
        progress_callback: ProgressCallback = None,
    ) -> List[Tuple[float, Dict[str, str]]]:
        cache_key = (str(question), int(top_k))
        cached = self._retrieval_cache.get(cache_key)
        if cached is not None:
            self._retrieval_cache.move_to_end(cache_key)
            self._last_search_timings = {
                "retrieval_cache_hit": 1.0,
                "lexical_seconds": 0.0,
                "query_embedding_seconds": 0.0,
                "candidate_embedding_seconds": 0.0,
                "scoring_seconds": 0.0,
                "retrieval_total_seconds": 0.0,
            }
            self._report(
                progress_callback,
                "Retrieval RAM cache hit: reused the previous result for this exact question.",
            )
            return self._restore_cached_hits(cached)

        total_started_at = time.perf_counter()

        lexical_started_at = time.perf_counter()
        self._report(progress_callback, "Finding lexical candidates...")
        lexical_candidates = self._lexical_candidates(question)
        lexical_seconds = time.perf_counter() - lexical_started_at
        self._report(
            progress_callback,
            (
                f"Lexical search: {lexical_seconds:.2f}s | "
                f"{len(lexical_candidates)} candidates"
            ),
        )
        if not lexical_candidates:
            raise RuntimeError(
                "No lexical candidates matched the question. "
                "Try a more specific term that appears in the documents."
            )

        query_embedding_started_at = time.perf_counter()
        self._report(progress_callback, "Embedding the question...")
        query_vector = self._embedding_model.embed_one(question).astype(np.float32)
        query_embedding_seconds = time.perf_counter() - query_embedding_started_at
        self._report(
            progress_callback,
            f"Query embedding: {query_embedding_seconds:.2f}s",
        )

        candidate_chunks = [chunk for _, chunk in lexical_candidates]
        candidate_embedding_started_at = time.perf_counter()
        self._report(
            progress_callback,
            f"Embedding {len(candidate_chunks)} retrieval candidates...",
        )
        candidate_vectors = self._embedding_model.embed_many(
            [chunk["text"] for chunk in candidate_chunks],
            progress_callback,
        ).astype(np.float32)
        candidate_embedding_seconds = (
            time.perf_counter() - candidate_embedding_started_at
        )
        self._report(
            progress_callback,
            f"Candidate embedding: {candidate_embedding_seconds:.2f}s",
        )

        scoring_started_at = time.perf_counter()
        query_norm = float(np.linalg.norm(query_vector))
        if query_norm <= 0.0:
            raise RuntimeError(
                "The embedding model returned an invalid question vector."
            )
        query_vector = query_vector / query_norm

        candidate_norms = np.linalg.norm(
            candidate_vectors,
            axis=1,
            keepdims=True,
        )
        candidate_norms[candidate_norms == 0.0] = 1.0
        normalized_candidates = candidate_vectors / candidate_norms
        semantic_scores = normalized_candidates @ query_vector

        lexical_ranks = [rank for rank, _ in lexical_candidates]
        best_rank = min(lexical_ranks)
        worst_rank = max(lexical_ranks)
        rank_range = worst_rank - best_rank

        combined: List[Tuple[float, Dict[str, str]]] = []
        for candidate_position, (lexical_rank, chunk) in enumerate(
            lexical_candidates
        ):
            if rank_range <= 1e-12:
                lexical_normalized = 1.0
            else:
                lexical_normalized = (
                    worst_rank - lexical_rank
                ) / rank_range
            semantic_normalized = (
                float(semantic_scores[candidate_position]) + 1.0
            ) / 2.0
            final_score = (
                0.35 * lexical_normalized
                + 0.65 * semantic_normalized
            )
            combined.append((final_score, chunk))

        combined.sort(key=lambda item: item[0], reverse=True)
        result = combined[: min(max(1, int(top_k)), len(combined))]
        scoring_seconds = time.perf_counter() - scoring_started_at
        total_seconds = time.perf_counter() - total_started_at

        self._last_search_timings = {
            "retrieval_cache_hit": 0.0,
            "lexical_seconds": lexical_seconds,
            "query_embedding_seconds": query_embedding_seconds,
            "candidate_embedding_seconds": candidate_embedding_seconds,
            "scoring_seconds": scoring_seconds,
            "retrieval_total_seconds": total_seconds,
        }
        self._report(
            progress_callback,
            (
                f"Retrieval total: {total_seconds:.2f}s | "
                f"scoring {scoring_seconds:.3f}s"
            ),
        )

        self._remember_retrieval(cache_key, result)
        return result

    def last_search_timings(self) -> Dict[str, float]:
        return dict(self._last_search_timings)

    def prepare_scope(self, root_folder, extensions):
        self._clear_retrieval_cache()
        return super().prepare_scope(root_folder, extensions)

    def store_file(self, source_path, signature, chunks) -> None:
        self._clear_retrieval_cache()
        super().store_file(source_path, signature, chunks)

    def mark_problem_file(
        self,
        source_path,
        signature,
        state,
        error_text,
    ):
        self._clear_retrieval_cache()
        return super().mark_problem_file(
            source_path,
            signature,
            state,
            error_text,
        )

    def finalize_scope(
        self,
        current_signatures,
        progress_callback=None,
        cancel_callback=None,
    ):
        self._clear_retrieval_cache()
        return super().finalize_scope(
            current_signatures,
            progress_callback,
            cancel_callback,
        )

    def _remember_retrieval(
        self,
        cache_key: Tuple[str, int],
        hits: List[Tuple[float, Dict[str, str]]],
    ) -> None:
        packed = tuple(
            (
                float(score),
                str(chunk["source_path"]),
                str(chunk["text"]),
            )
            for score, chunk in hits
        )
        self._retrieval_cache[cache_key] = packed
        self._retrieval_cache.move_to_end(cache_key)
        while len(self._retrieval_cache) > self._RETRIEVAL_CACHE_LIMIT:
            self._retrieval_cache.popitem(last=False)

    def _restore_cached_hits(
        self,
        cached: Tuple[Tuple[float, str, str], ...],
    ) -> List[Tuple[float, Dict[str, str]]]:
        return [
            (
                score,
                {
                    "source_path": source_path,
                    "text": text,
                },
            )
            for score, source_path, text in cached
        ]

    def _clear_retrieval_cache(self) -> None:
        self._retrieval_cache.clear()

    @staticmethod
    def _report(
        progress_callback: ProgressCallback,
        message: str,
    ) -> None:
        if progress_callback is not None:
            progress_callback(message)
