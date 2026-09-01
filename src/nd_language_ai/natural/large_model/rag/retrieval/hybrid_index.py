import re
import sqlite3
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

import numpy as np

from nd_language_ai.natural.large_model.rag.retrieval.embedding_model import (
    EmbeddingModel,
    ProgressCallback,
)


CancelCallback = Optional[Callable[[], bool]]
FileSignature = Tuple[int, int]


class HybridIndex:
    _SCHEMA_VERSION = "1"

    def __init__(
        self,
        embedding_model: EmbeddingModel,
        candidate_count: int,
        database_path: Optional[Path] = None,
    ) -> None:
        self._embedding_model = embedding_model
        self._candidate_count = max(8, int(candidate_count))
        self._database_path = (
            Path(database_path).expanduser()
            if database_path is not None
            else self._default_database_path()
        )
        self._stop_words = {
            "a", "an", "and", "are", "as", "at", "be", "by", "for", "from",
            "how", "in", "is", "it", "of", "on", "or", "that", "the", "this",
            "to", "was", "what", "when", "where", "which", "who", "why", "with",
        }
        self._initialize_database()

    def file_signatures(self) -> Dict[str, FileSignature]:
        with self._connect() as connection:
            rows = connection.execute("SELECT path, mtime_ns, size FROM files").fetchall()
        return {
            str(path): (int(mtime_ns), int(size))
            for path, mtime_ns, size in rows
        }

    def store_file(
        self,
        source_path: str,
        signature: FileSignature,
        chunks: List[str],
    ) -> None:
        with self._connect() as connection:
            self._replace_file(connection, source_path, signature, chunks)
            connection.commit()

    def finalize_scope(
        self,
        current_signatures: Dict[str, FileSignature],
        progress_callback: ProgressCallback = None,
        cancel_callback: CancelCallback = None,
    ) -> Dict[str, int]:
        self._raise_if_cancelled(cancel_callback)
        with self._connect() as connection:
            connection.execute("UPDATE files SET active = 0")
            activation_rows = [
                (path, int(signature[0]), int(signature[1]))
                for path, signature in current_signatures.items()
            ]
            connection.executemany(
                """
                UPDATE files
                SET active = 1
                WHERE path = ? AND mtime_ns = ? AND size = ?
                """,
                activation_rows,
            )
            connection.commit()
            active_file_count = int(
                connection.execute(
                    """
                    SELECT COUNT(DISTINCT c.source_path)
                    FROM chunks AS c
                    JOIN files AS f ON f.path = c.source_path
                    WHERE f.active = 1
                    """
                ).fetchone()[0]
            )
            active_chunk_count = int(
                connection.execute(
                    """
                    SELECT COUNT(*)
                    FROM chunks AS c
                    JOIN files AS f ON f.path = c.source_path
                    WHERE f.active = 1
                    """
                ).fetchone()[0]
            )
        if progress_callback is not None:
            progress_callback(
                f"Persistent index ready: {active_file_count} files, {active_chunk_count} chunks."
            )
        return {"file_count": active_file_count, "chunk_count": active_chunk_count}

    def synchronize(
        self,
        current_signatures: Dict[str, FileSignature],
        updated_chunks: Dict[str, List[str]],
        failed_paths: set[str],
        progress_callback: ProgressCallback = None,
        cancel_callback: CancelCallback = None,
    ) -> Dict[str, int]:
        for source_path, chunks in updated_chunks.items():
            self._raise_if_cancelled(cancel_callback)
            self.store_file(source_path, current_signatures[source_path], chunks)
        result = self.finalize_scope(current_signatures, progress_callback, cancel_callback)
        result["updated_file_count"] = len(updated_chunks)
        result["reused_file_count"] = max(
            0, len(current_signatures) - len(updated_chunks) - len(failed_paths)
        )
        return result

    def build(
        self,
        chunks: List[Dict[str, str]],
        progress_callback: ProgressCallback = None,
        cancel_callback: CancelCallback = None,
    ) -> None:
        if not chunks:
            raise RuntimeError("No document chunks were created from the selected files.")
        grouped_chunks: Dict[str, List[str]] = {}
        for chunk in chunks:
            source_path = str(chunk.get("source_path", ""))
            text = str(chunk.get("text", ""))
            if not source_path or not text:
                continue
            grouped_chunks.setdefault(source_path, []).append(text)
        if not grouped_chunks:
            raise RuntimeError("No valid document chunks were provided for indexing.")
        signatures = {source_path: (0, 0) for source_path in grouped_chunks}
        for source_path, source_chunks in grouped_chunks.items():
            self.store_file(source_path, signatures[source_path], source_chunks)
        self.finalize_scope(signatures, progress_callback, cancel_callback)

    def search(
        self,
        question: str,
        top_k: int,
        progress_callback: ProgressCallback = None,
    ) -> List[Tuple[float, Dict[str, str]]]:
        if progress_callback is not None:
            progress_callback("Finding lexical candidates...")
        lexical_candidates = self._lexical_candidates(question)
        if not lexical_candidates:
            raise RuntimeError(
                "No lexical candidates matched the question. Try a more specific term that appears in the documents."
            )
        if progress_callback is not None:
            progress_callback(f"Semantic reranking {len(lexical_candidates)} candidates...")
        query_vector = self._embedding_model.embed_one(question).astype(np.float32)
        candidate_chunks = [chunk for _, chunk in lexical_candidates]
        candidate_vectors = self._embedding_model.embed_many(
            [chunk["text"] for chunk in candidate_chunks], progress_callback
        ).astype(np.float32)
        query_norm = float(np.linalg.norm(query_vector))
        if query_norm <= 0.0:
            raise RuntimeError("The embedding model returned an invalid question vector.")
        query_vector = query_vector / query_norm
        candidate_norms = np.linalg.norm(candidate_vectors, axis=1, keepdims=True)
        candidate_norms[candidate_norms == 0.0] = 1.0
        normalized_candidates = candidate_vectors / candidate_norms
        semantic_scores = normalized_candidates @ query_vector
        lexical_ranks = [rank for rank, _ in lexical_candidates]
        best_rank = min(lexical_ranks)
        worst_rank = max(lexical_ranks)
        rank_range = worst_rank - best_rank
        combined: List[Tuple[float, Dict[str, str]]] = []
        for candidate_position, (lexical_rank, chunk) in enumerate(lexical_candidates):
            if rank_range <= 1e-12:
                lexical_normalized = 1.0
            else:
                lexical_normalized = (worst_rank - lexical_rank) / rank_range
            semantic_normalized = (float(semantic_scores[candidate_position]) + 1.0) / 2.0
            final_score = 0.35 * lexical_normalized + 0.65 * semantic_normalized
            combined.append((final_score, chunk))
        combined.sort(key=lambda item: item[0], reverse=True)
        return combined[: min(max(1, int(top_k)), len(combined))]

    def _lexical_candidates(
        self,
        question: str,
    ) -> List[Tuple[float, Dict[str, str]]]:
        query_terms = self._tokenize(question)
        if not query_terms:
            return []
        match_expression = " OR ".join(f'"{term}"' for term in dict.fromkeys(query_terms))
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    bm25(chunks_fts, 1.0, 1.0) AS lexical_rank,
                    c.source_path,
                    c.text
                FROM chunks_fts
                JOIN chunks AS c ON c.id = chunks_fts.rowid
                JOIN files AS f ON f.path = c.source_path
                WHERE chunks_fts MATCH ?
                  AND f.active = 1
                ORDER BY lexical_rank ASC
                LIMIT ?
                """,
                (match_expression, self._candidate_count),
            ).fetchall()
        return [
            (float(lexical_rank), {"source_path": str(source_path), "text": str(text)})
            for lexical_rank, source_path, text in rows
        ]

    def _replace_file(
        self,
        connection: sqlite3.Connection,
        source_path: str,
        signature: FileSignature,
        chunks: List[str],
    ) -> None:
        connection.execute(
            """
            DELETE FROM chunks_fts
            WHERE rowid IN (
                SELECT id FROM chunks WHERE source_path = ?
            )
            """,
            (source_path,),
        )
        connection.execute("DELETE FROM chunks WHERE source_path = ?", (source_path,))
        connection.execute(
            """
            INSERT INTO files(path, mtime_ns, size, active)
            VALUES (?, ?, ?, 0)
            ON CONFLICT(path) DO UPDATE SET
                mtime_ns = excluded.mtime_ns,
                size = excluded.size
            """,
            (source_path, int(signature[0]), int(signature[1])),
        )
        if not chunks:
            return
        connection.executemany(
            "INSERT INTO chunks(source_path, text) VALUES (?, ?)",
            [(source_path, chunk_text) for chunk_text in chunks],
        )
        connection.execute(
            """
            INSERT INTO chunks_fts(rowid, source_path, text)
            SELECT id, source_path, text
            FROM chunks
            WHERE source_path = ?
            """,
            (source_path,),
        )

    def _initialize_database(self) -> None:
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )
            stored_version_row = connection.execute(
                "SELECT value FROM metadata WHERE key = 'schema_version'"
            ).fetchone()
            stored_version = str(stored_version_row[0]) if stored_version_row is not None else None
            if stored_version != self._SCHEMA_VERSION:
                connection.execute("DROP TABLE IF EXISTS chunks_fts")
                connection.execute("DROP TABLE IF EXISTS chunks")
                connection.execute("DROP TABLE IF EXISTS files")
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS files(
                    path TEXT PRIMARY KEY,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_path TEXT NOT NULL,
                    text TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS chunks_source_path_index
                ON chunks(source_path)
                """
            )
            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                USING fts5(
                    source_path,
                    text,
                    tokenize = 'unicode61 remove_diacritics 2'
                )
                """
            )
            connection.execute(
                """
                INSERT INTO metadata(key, value)
                VALUES ('schema_version', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (self._SCHEMA_VERSION,),
            )
            connection.commit()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path, timeout=30.0)
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA temp_store = MEMORY")
        return connection

    def _default_database_path(self) -> Path:
        return Path.home() / ".cache" / "nd_language_ai_project" / "rag_index.sqlite3"

    def _tokenize(self, text: str) -> List[str]:
        tokens = re.findall(r"\w+", text.lower(), flags=re.UNICODE)
        return [token for token in tokens if len(token) >= 2 and token not in self._stop_words]

    def _raise_if_cancelled(self, cancel_callback: CancelCallback) -> None:
        if cancel_callback is not None and cancel_callback():
            raise InterruptedError("Index build cancelled.")
