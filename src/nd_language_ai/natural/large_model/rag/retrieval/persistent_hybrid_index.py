import json
import sqlite3
from pathlib import Path

from nd_language_ai.natural.large_model.rag.retrieval.hybrid_index import HybridIndex


class PersistentHybridIndex(HybridIndex):
    _SCHEMA_VERSION = "3"

    def __init__(self, *args, **kwargs):
        self._pending_root = ""
        self._pending_extensions = []

        database_path = kwargs.get("database_path")
        if database_path is None:
            database_path = (
                Path.home()
                / ".cache"
                / "nd_language_ai_project"
                / "rag_index.sqlite3"
            )
        else:
            database_path = Path(database_path).expanduser()

        kwargs["database_path"] = database_path
        self._remove_obsolete_database_if_needed(database_path)
        super().__init__(*args, **kwargs)

    def prepare_scope(self, root_folder, extensions):
        self._pending_root = str(
            Path(root_folder).expanduser().resolve()
        )
        self._pending_extensions = self._normalize_extensions(
            extensions
        )

    def cached_scope_summary(
        self,
        root_folder,
        extensions,
        adopt_legacy_scope=False,
    ):
        root_folder = str(
            Path(root_folder).expanduser().resolve()
        )
        extensions = self._normalize_extensions(extensions)

        with self._connect() as connection:
            active_root = self._metadata(
                connection,
                "active_root_folder",
            )
            active_extensions_text = self._metadata(
                connection,
                "active_extensions",
            )

            try:
                active_extensions = (
                    json.loads(active_extensions_text)
                    if active_extensions_text
                    else []
                )
            except json.JSONDecodeError:
                active_extensions = []

            if (
                active_root != root_folder
                or active_extensions != extensions
            ):
                return {
                    "usable": False,
                    "file_count": 0,
                    "chunk_count": 0,
                }

            file_count, chunk_count = self._active_counts(
                connection
            )

        return {
            "usable": file_count > 0,
            "file_count": file_count,
            "chunk_count": chunk_count,
        }

    def mark_problem_file(
        self,
        source_path,
        signature,
        state,
        error_text,
    ):
        state = "stalled" if state == "stalled" else "failed"

        with self._connect() as connection:
            file_id = self._ensure_file_row(
                connection,
                source_path,
                signature,
                state,
                str(error_text)[:1200],
            )
            connection.execute(
                "DELETE FROM chunks WHERE file_id = ?",
                (file_id,),
            )
            connection.commit()
            self._checkpoint_and_reclaim(connection)

    def finalize_scope(
        self,
        current_signatures,
        progress_callback=None,
        cancel_callback=None,
    ):
        self._raise_if_cancelled(cancel_callback)

        with self._connect() as connection:
            connection.execute(
                "CREATE TEMP TABLE IF NOT EXISTS "
                "current_scope_paths(path TEXT PRIMARY KEY)"
            )
            connection.execute(
                "DELETE FROM current_scope_paths"
            )
            connection.executemany(
                "INSERT OR IGNORE INTO current_scope_paths(path) "
                "VALUES (?)",
                [(path,) for path in current_signatures],
            )

            connection.execute(
                """
                DELETE FROM files
                WHERE path NOT IN (
                    SELECT path FROM current_scope_paths
                )
                """
            )

            connection.execute(
                "UPDATE files SET active = 0"
            )
            connection.executemany(
                """
                UPDATE files
                SET active = 1
                WHERE path = ?
                  AND mtime_ns = ?
                  AND size = ?
                  AND state = 'cached'
                """,
                [
                    (
                        path,
                        int(signature[0]),
                        int(signature[1]),
                    )
                    for path, signature
                    in current_signatures.items()
                ],
            )

            if self._pending_root:
                self._save_scope(
                    connection,
                    self._pending_root,
                    self._pending_extensions,
                )

            connection.commit()
            file_count, chunk_count = self._active_counts(
                connection
            )
            self._checkpoint_and_reclaim(connection)

        if progress_callback:
            progress_callback(
                f"Persistent index ready: {file_count} files, "
                f"{chunk_count} chunks."
            )

        return {
            "file_count": file_count,
            "chunk_count": chunk_count,
        }

    def _replace_file(
        self,
        connection,
        source_path,
        signature,
        chunks,
    ):
        file_id = self._ensure_file_row(
            connection,
            source_path,
            signature,
            "cached",
            "",
        )

        connection.execute(
            "DELETE FROM chunks WHERE file_id = ?",
            (file_id,),
        )

        if chunks:
            connection.executemany(
                "INSERT INTO chunks(file_id, text) "
                "VALUES (?, ?)",
                [
                    (file_id, chunk_text)
                    for chunk_text in chunks
                ],
            )

    def _lexical_candidates(self, question):
        query_terms = self._tokenize(question)
        if not query_terms:
            return []

        match_expression = " OR ".join(
            f'"{term}"'
            for term in dict.fromkeys(query_terms)
        )

        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT
                    bm25(chunks_fts) AS lexical_rank,
                    f.path,
                    c.text
                FROM chunks_fts
                JOIN chunks AS c
                    ON c.id = chunks_fts.rowid
                JOIN files AS f
                    ON f.id = c.file_id
                WHERE chunks_fts MATCH ?
                  AND f.active = 1
                  AND f.state = 'cached'
                ORDER BY lexical_rank ASC
                LIMIT ?
                """,
                (
                    match_expression,
                    self._candidate_count,
                ),
            ).fetchall()

        return [
            (
                float(lexical_rank),
                {
                    "source_path": str(source_path),
                    "text": str(text),
                },
            )
            for lexical_rank, source_path, text in rows
        ]

    def _initialize_database(self):
        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with self._connect() as connection:
            connection.execute(
                "PRAGMA auto_vacuum = INCREMENTAL"
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS metadata(
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS files(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    path TEXT NOT NULL UNIQUE,
                    mtime_ns INTEGER NOT NULL,
                    size INTEGER NOT NULL,
                    active INTEGER NOT NULL DEFAULT 0,
                    state TEXT NOT NULL DEFAULT 'cached',
                    error TEXT NOT NULL DEFAULT ''
                )
                """
            )

            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks(
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    file_id INTEGER NOT NULL,
                    text TEXT NOT NULL,
                    FOREIGN KEY(file_id)
                        REFERENCES files(id)
                        ON DELETE CASCADE
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    chunks_file_id_index
                ON chunks(file_id)
                """
            )

            connection.execute(
                """
                CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts
                USING fts5(
                    text,
                    content = 'chunks',
                    content_rowid = 'id',
                    tokenize = 'unicode61 remove_diacritics 2'
                )
                """
            )

            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS chunks_ai
                AFTER INSERT ON chunks
                BEGIN
                    INSERT INTO chunks_fts(rowid, text)
                    VALUES (new.id, new.text);
                END
                """
            )

            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS chunks_ad
                AFTER DELETE ON chunks
                BEGIN
                    INSERT INTO chunks_fts(
                        chunks_fts,
                        rowid,
                        text
                    )
                    VALUES (
                        'delete',
                        old.id,
                        old.text
                    );
                END
                """
            )

            connection.execute(
                """
                CREATE TRIGGER IF NOT EXISTS chunks_au
                AFTER UPDATE ON chunks
                BEGIN
                    INSERT INTO chunks_fts(
                        chunks_fts,
                        rowid,
                        text
                    )
                    VALUES (
                        'delete',
                        old.id,
                        old.text
                    );
                    INSERT INTO chunks_fts(rowid, text)
                    VALUES (new.id, new.text);
                END
                """
            )

            connection.execute(
                """
                INSERT INTO metadata(key, value)
                VALUES ('schema_version', ?)
                ON CONFLICT(key)
                DO UPDATE SET value = excluded.value
                """,
                (self._SCHEMA_VERSION,),
            )

            connection.commit()

    def _connect(self):
        connection = sqlite3.connect(
            self._database_path,
            timeout=30.0,
        )
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA synchronous = NORMAL")
        connection.execute("PRAGMA temp_store = MEMORY")
        return connection

    def _ensure_file_row(
        self,
        connection,
        source_path,
        signature,
        state,
        error_text,
    ):
        connection.execute(
            """
            INSERT INTO files(
                path,
                mtime_ns,
                size,
                active,
                state,
                error
            )
            VALUES (?, ?, ?, 0, ?, ?)
            ON CONFLICT(path)
            DO UPDATE SET
                mtime_ns = excluded.mtime_ns,
                size = excluded.size,
                active = 0,
                state = excluded.state,
                error = excluded.error
            """,
            (
                source_path,
                int(signature[0]),
                int(signature[1]),
                state,
                error_text,
            ),
        )

        row = connection.execute(
            "SELECT id FROM files WHERE path = ?",
            (source_path,),
        ).fetchone()

        if row is None:
            raise RuntimeError(
                f"Could not create cache row for {source_path}"
            )

        return int(row[0])

    def _active_counts(self, connection):
        file_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM files
                WHERE active = 1
                  AND state = 'cached'
                """
            ).fetchone()[0]
        )

        chunk_count = int(
            connection.execute(
                """
                SELECT COUNT(*)
                FROM chunks AS c
                JOIN files AS f
                    ON f.id = c.file_id
                WHERE f.active = 1
                  AND f.state = 'cached'
                """
            ).fetchone()[0]
        )

        return file_count, chunk_count

    def _save_scope(
        self,
        connection,
        root_folder,
        extensions,
    ):
        connection.executemany(
            """
            INSERT INTO metadata(key, value)
            VALUES (?, ?)
            ON CONFLICT(key)
            DO UPDATE SET value = excluded.value
            """,
            [
                (
                    "active_root_folder",
                    root_folder,
                ),
                (
                    "active_extensions",
                    json.dumps(
                        extensions,
                        separators=(",", ":"),
                    ),
                ),
            ],
        )

    def _metadata(self, connection, key):
        row = connection.execute(
            "SELECT value FROM metadata WHERE key = ?",
            (key,),
        ).fetchone()
        return str(row[0]) if row else ""

    def _normalize_extensions(self, extensions):
        result = set()
        for extension in extensions:
            value = str(extension).strip().lower()
            if not value:
                continue
            result.add(
                value
                if value.startswith(".")
                else "." + value
            )
        return sorted(result)

    def _checkpoint_and_reclaim(self, connection):
        try:
            connection.execute("PRAGMA optimize")
        except sqlite3.DatabaseError:
            pass

        try:
            free_pages = int(
                connection.execute(
                    "PRAGMA freelist_count"
                ).fetchone()[0]
            )
            if free_pages > 0:
                pages_to_reclaim = min(
                    free_pages,
                    50000,
                )
                connection.execute(
                    f"PRAGMA incremental_vacuum({pages_to_reclaim})"
                )
        except sqlite3.DatabaseError:
            pass

        try:
            connection.execute(
                "PRAGMA wal_checkpoint(TRUNCATE)"
            )
        except sqlite3.DatabaseError:
            pass

    def _remove_obsolete_database_if_needed(
        self,
        database_path,
    ):
        database_path = Path(database_path)

        if not database_path.exists():
            self._remove_sqlite_sidecars(database_path)
            return

        schema_version = ""
        try:
            connection = sqlite3.connect(
                f"file:{database_path}?mode=ro",
                uri=True,
                timeout=2.0,
            )
            try:
                row = connection.execute(
                    """
                    SELECT value
                    FROM metadata
                    WHERE key = 'schema_version'
                    """
                ).fetchone()
                schema_version = (
                    str(row[0])
                    if row
                    else ""
                )
            finally:
                connection.close()
        except sqlite3.DatabaseError:
            schema_version = ""

        if schema_version == self._SCHEMA_VERSION:
            return

        self._remove_file_if_exists(database_path)
        self._remove_sqlite_sidecars(database_path)

    def _remove_sqlite_sidecars(self, database_path):
        self._remove_file_if_exists(
            Path(str(database_path) + "-wal")
        )
        self._remove_file_if_exists(
            Path(str(database_path) + "-shm")
        )

    def _remove_file_if_exists(self, path):
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
