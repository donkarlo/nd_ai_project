import json
import sqlite3
from pathlib import Path
from typing import Dict, List

from nd_language_ai.natural.large_model.rag.retrieval.persistent_hybrid_index import (
    PersistentHybridIndex,
)
from nd_language_ai.natural.large_model.rag.service.rag_service import (
    CancelCallback,
    FileSignature,
    ProgressCallback,
    RagService,
)


class PersistentRagService(RagService):
    _SCHEMA_VERSION = "3"
    _SQLITE_CANCEL_PROGRESS_OPCODES = 200
    _DEFAULT_DATABASE_PATH = (
        Path.home()
        / ".cache"
        / "nd_language_ai_project"
        / "rag_index.sqlite3"
    )

    @classmethod
    def inspect_cached_scope(
        cls,
        root_folder: str,
        extensions: List[str],
        delete_unusable: bool = True,
    ) -> Dict[str, object]:
        database_path = cls._DEFAULT_DATABASE_PATH
        root_path = str(Path(root_folder).expanduser().resolve())
        normalized_extensions = cls._normalize_extensions_static(extensions)

        result = {
            "usable": False,
            "file_count": 0,
            "chunk_count": 0,
            "cleanup_performed": False,
        }

        if not database_path.exists():
            cls._remove_sqlite_sidecars(database_path)
            return result

        unusable = False
        try:
            connection = sqlite3.connect(
                f"file:{database_path}?mode=ro",
                uri=True,
                timeout=2.0,
            )
            try:
                schema_version = cls._metadata_value(
                    connection,
                    "schema_version",
                )
                active_root = cls._metadata_value(
                    connection,
                    "active_root_folder",
                )
                active_extensions_text = cls._metadata_value(
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
                    schema_version != cls._SCHEMA_VERSION
                    or active_root != root_path
                    or active_extensions != normalized_extensions
                ):
                    unusable = True
                else:
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

                    if file_count > 0 and chunk_count > 0:
                        result.update(
                            {
                                "usable": True,
                                "file_count": file_count,
                                "chunk_count": chunk_count,
                            }
                        )
                    else:
                        unusable = True
            finally:
                connection.close()
        except (sqlite3.DatabaseError, OSError):
            unusable = True

        if unusable and delete_unusable:
            cls._remove_database_files(database_path)
            result["cleanup_performed"] = True

        return result

    def use_cached_index(
        self,
        root_folder: str,
        extensions: List[str],
    ) -> Dict[str, object]:
        index = self._persistent_index()
        summary = index.cached_scope_summary(
            root_folder,
            extensions,
            adopt_legacy_scope=True,
        )
        self._index_ready = bool(summary.get("usable", False))
        return summary

    def reset_index_cache(self) -> None:
        index = self._persistent_index()
        self._remove_database_files(index._database_path)
        index._initialize_database()
        self._index_ready = False

    def build_index(
        self,
        root_folder: str,
        extensions: List[str],
        progress_callback=None,
        cancel_callback=None,
    ) -> Dict[str, object]:
        self._persistent_index().prepare_scope(root_folder, extensions)
        return super().build_index(
            root_folder,
            extensions,
            progress_callback,
            cancel_callback,
        )

    def _read_and_chunk_document(
        self,
        file_path: Path,
        cancel_callback: CancelCallback = None,
    ) -> List[str]:
        try:
            return super()._read_and_chunk_document(
                file_path,
                cancel_callback,
            )
        except InterruptedError:
            raise
        except Exception as error:
            self._raise_if_cancelled(cancel_callback)
            try:
                stat_result = file_path.stat()
                signature = (
                    int(stat_result.st_mtime_ns),
                    int(stat_result.st_size),
                )
                state = (
                    "stalled"
                    if isinstance(error, TimeoutError)
                    else "failed"
                )
                self._persistent_index().mark_problem_file(
                    str(file_path),
                    signature,
                    state,
                    str(error),
                )
            except OSError:
                pass
            raise

    def _store_file(
        self,
        source_path: str,
        signature: FileSignature,
        chunks: List[str],
        cancel_callback: CancelCallback,
    ) -> None:
        self._raise_if_cancelled(cancel_callback)
        index = self._persistent_index()

        with index._connect() as connection:
            self._install_cancel_handler(connection, cancel_callback)
            try:
                index._replace_file(
                    connection,
                    source_path,
                    signature,
                    chunks,
                )
                self._raise_if_cancelled(cancel_callback)
                connection.commit()
            except InterruptedError:
                connection.rollback()
                raise
            except sqlite3.OperationalError as error:
                connection.rollback()
                if cancel_callback is not None and cancel_callback():
                    raise InterruptedError("Index build cancelled.") from error
                raise
            finally:
                connection.set_progress_handler(None, 0)

    def _finalize_index_scope(
        self,
        current_signatures: Dict[str, FileSignature],
        progress_callback: ProgressCallback,
        cancel_callback: CancelCallback,
    ) -> Dict[str, int]:
        self._raise_if_cancelled(cancel_callback)
        index = self._persistent_index()

        with index._connect() as connection:
            self._install_cancel_handler(connection, cancel_callback)
            try:
                connection.execute(
                    "CREATE TEMP TABLE IF NOT EXISTS "
                    "current_scope_paths(path TEXT PRIMARY KEY)"
                )
                connection.execute("DELETE FROM current_scope_paths")

                path_rows = []
                for path in current_signatures:
                    self._raise_if_cancelled(cancel_callback)
                    path_rows.append((path,))
                connection.executemany(
                    "INSERT OR IGNORE INTO current_scope_paths(path) VALUES (?)",
                    path_rows,
                )

                self._raise_if_cancelled(cancel_callback)
                connection.execute(
                    """
                    DELETE FROM files
                    WHERE path NOT IN (
                        SELECT path FROM current_scope_paths
                    )
                    """
                )
                connection.execute("UPDATE files SET active = 0")

                activation_rows = []
                for path, signature in current_signatures.items():
                    self._raise_if_cancelled(cancel_callback)
                    activation_rows.append(
                        (
                            path,
                            int(signature[0]),
                            int(signature[1]),
                        )
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
                    activation_rows,
                )

                if index._pending_root:
                    index._save_scope(
                        connection,
                        index._pending_root,
                        index._pending_extensions,
                    )

                self._raise_if_cancelled(cancel_callback)
                connection.commit()
                file_count, chunk_count = index._active_counts(connection)
            except InterruptedError:
                connection.rollback()
                raise
            except sqlite3.OperationalError as error:
                connection.rollback()
                if cancel_callback is not None and cancel_callback():
                    raise InterruptedError("Index build cancelled.") from error
                raise
            finally:
                connection.set_progress_handler(None, 0)

        if progress_callback is not None:
            progress_callback(
                f"Persistent index ready: {file_count} files, "
                f"{chunk_count} chunks."
            )

        return {
            "file_count": int(file_count),
            "chunk_count": int(chunk_count),
        }

    def _install_cancel_handler(
        self,
        connection: sqlite3.Connection,
        cancel_callback: CancelCallback,
    ) -> None:
        if cancel_callback is None:
            return
        connection.set_progress_handler(
            lambda: 1 if cancel_callback() else 0,
            self._SQLITE_CANCEL_PROGRESS_OPCODES,
        )

    def _persistent_index(self) -> PersistentHybridIndex:
        if not isinstance(self._retrieval_index, PersistentHybridIndex):
            raise TypeError(
                "PersistentRagService requires PersistentHybridIndex"
            )
        return self._retrieval_index

    @classmethod
    def _remove_database_files(cls, database_path: Path) -> None:
        database_path = Path(database_path)
        cls._remove_file(database_path)
        cls._remove_sqlite_sidecars(database_path)

    @classmethod
    def _remove_sqlite_sidecars(cls, database_path: Path) -> None:
        cls._remove_file(Path(str(database_path) + "-wal"))
        cls._remove_file(Path(str(database_path) + "-shm"))

    @staticmethod
    def _remove_file(path: Path) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass

    @staticmethod
    def _metadata_value(
        connection: sqlite3.Connection,
        key: str,
    ) -> str:
        try:
            row = connection.execute(
                "SELECT value FROM metadata WHERE key = ?",
                (key,),
            ).fetchone()
        except sqlite3.DatabaseError:
            return ""
        return str(row[0]) if row else ""

    @staticmethod
    def _normalize_extensions_static(
        extensions: List[str],
    ) -> List[str]:
        normalized = set()
        for extension in extensions:
            value = str(extension).strip().lower()
            if not value:
                continue
            normalized.add(
                value
                if value.startswith(".")
                else "." + value
            )
        return sorted(normalized)
