import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Callable, Dict, List, Optional, Set, Tuple

from nd_language_ai.natural.large_model.rag.document.file_crawler import FileCrawler
from nd_language_ai.natural.large_model.rag.model.language_model import LanguageModel
from nd_language_ai.natural.large_model.rag.retrieval.chunker import Chunker
from nd_language_ai.natural.large_model.rag.retrieval.hybrid_index import HybridIndex


ProgressCallback = Optional[Callable[[str], None]]
TokenCallback = Optional[Callable[[str], None]]
CancelCallback = Optional[Callable[[], bool]]
FileSignature = Tuple[int, int]


class RagService:
    _FILE_READ_TIMEOUT_SECONDS = 60.0
    _SUBPROCESS_POLL_SECONDS = 0.10

    def __init__(
        self,
        crawler: FileCrawler,
        chunker: Chunker,
        retrieval_index: HybridIndex,
        language_model: LanguageModel,
        top_k: int,
        max_context_chunks: int,
    ) -> None:
        self._crawler = crawler
        self._chunker = chunker
        self._retrieval_index = retrieval_index
        self._language_model = language_model
        self._top_k = int(top_k)
        self._max_context_chunks = int(max_context_chunks)
        self._index_ready = False

    def build_index(
        self,
        root_folder: str,
        extensions: List[str],
        progress_callback: ProgressCallback = None,
        cancel_callback: CancelCallback = None,
    ) -> Dict[str, object]:
        root_path = Path(root_folder).expanduser().resolve()
        if not root_path.exists() or not root_path.is_dir():
            raise ValueError(f"Root folder does not exist: {root_path}")

        allowed_extensions = self._normalize_extensions(extensions)
        if not allowed_extensions:
            raise ValueError("Add at least one file extension before building the index.")

        extension_text = ", ".join(sorted(allowed_extensions))
        self._report(
            progress_callback,
            f"Scanning for selected extensions only: {extension_text}",
        )

        file_paths: List[Path] = []
        for file_path in self._crawler.iter_files(root_path, allowed_extensions):
            self._raise_if_cancelled(cancel_callback)
            file_paths.append(file_path)
            if len(file_paths) % 1000 == 0:
                self._report(
                    progress_callback,
                    f"Found {len(file_paths)} matching files so far...",
                )

        total_files = len(file_paths)
        self._report(
            progress_callback,
            f"Found {total_files} matching files ({extension_text}).",
        )
        if not file_paths:
            raise RuntimeError(
                "No files matched the selected extensions under the root folder."
            )

        current_signatures: Dict[str, FileSignature] = {}
        skipped_files: List[str] = []
        for file_index, file_path in enumerate(file_paths, start=1):
            self._raise_if_cancelled(cancel_callback)
            try:
                stat_result = file_path.stat()
            except OSError as error:
                skipped_files.append(f"{file_path}: {error}")
                continue
            current_signatures[str(file_path)] = (
                int(stat_result.st_mtime_ns),
                int(stat_result.st_size),
            )
            if file_index == total_files or file_index % 1000 == 0:
                self._report(
                    progress_callback,
                    f"Checked metadata for {file_index}/{total_files} files...",
                )

        self._raise_if_cancelled(cancel_callback)
        cached_signatures = self._retrieval_index.file_signatures()
        changed_paths = [
            file_path
            for file_path in file_paths
            if str(file_path) in current_signatures
            and cached_signatures.get(str(file_path))
            != current_signatures[str(file_path)]
        ]
        reused_file_count = len(current_signatures) - len(changed_paths)
        self._report(
            progress_callback,
            (
                f"Incremental update: {len(changed_paths)} changed/new files, "
                f"{reused_file_count} files already cached."
            ),
        )

        try:
            process_result = self._process_changed_files(
                changed_paths,
                current_signatures,
                progress_callback,
                cancel_callback,
            )
            self._raise_if_cancelled(cancel_callback)
            sync_result = self._finalize_index_scope(
                current_signatures,
                progress_callback,
                cancel_callback,
            )
        except InterruptedError:
            self._report(
                progress_callback,
                "Indexing cancelled immediately. No expensive finalization was run.",
            )
            raise

        file_count = int(sync_result["file_count"])
        chunk_count = int(sync_result["chunk_count"])
        failed_files = list(process_result["failed_files"])
        stalled_files = list(process_result["stalled_files"])
        skipped_files.extend(failed_files)
        skipped_files.extend(stalled_files)

        self._index_ready = file_count > 0
        if not self._index_ready:
            raise RuntimeError(
                "No readable files matched the selected extensions under the root folder."
            )

        return {
            "root_folder": str(root_path),
            "extensions": sorted(allowed_extensions),
            "file_count": file_count,
            "matched_file_count": total_files,
            "chunk_count": chunk_count,
            "updated_file_count": int(process_result["saved_file_count"]),
            "reused_file_count": reused_file_count,
            "failed_file_count": len(failed_files),
            "stalled_file_count": len(stalled_files),
            "failed_files": failed_files,
            "stalled_files": stalled_files,
            "skipped_files": skipped_files,
            "cancelled": False,
        }

    def _process_changed_files(
        self,
        changed_paths: List[Path],
        current_signatures: Dict[str, FileSignature],
        progress_callback: ProgressCallback,
        cancel_callback: CancelCallback,
    ) -> Dict[str, object]:
        if not changed_paths:
            return {
                "saved_file_count": 0,
                "failed_files": [],
                "stalled_files": [],
            }

        total_changed = len(changed_paths)
        saved_file_count = 0
        failed_files: List[str] = []
        stalled_files: List[str] = []

        for completed_count, file_path in enumerate(changed_paths, start=1):
            self._raise_if_cancelled(cancel_callback)
            source_path = str(file_path)
            issue_text = ""

            try:
                chunks = self._read_and_chunk_document(
                    file_path,
                    cancel_callback,
                )
                self._raise_if_cancelled(cancel_callback)

                store_started_at = time.monotonic()
                self._store_file(
                    source_path,
                    current_signatures[source_path],
                    chunks,
                    cancel_callback,
                )
                self._raise_if_cancelled(cancel_callback)

                store_seconds = time.monotonic() - store_started_at
                saved_file_count += 1
                if store_seconds >= 5.0:
                    issue_text = f" | DB write {store_seconds:.1f}s"
            except InterruptedError:
                raise
            except TimeoutError as error:
                error_text = self._short_error(error)
                stalled_files.append(f"{file_path}: {error_text}")
                issue_text = f" | STALLED: {error_text}"
            except Exception as error:
                error_text = self._short_error(error)
                failed_files.append(f"{file_path}: {error_text}")
                issue_text = f" | FAILED: {error_text}"

            self._report_progress_counts(
                progress_callback,
                completed_count,
                total_changed,
                saved_file_count,
                len(failed_files),
                len(stalled_files),
                file_path.name,
                issue_text,
            )

        return {
            "saved_file_count": saved_file_count,
            "failed_files": failed_files,
            "stalled_files": stalled_files,
        }

    def _store_file(
        self,
        source_path: str,
        signature: FileSignature,
        chunks: List[str],
        cancel_callback: CancelCallback,
    ) -> None:
        self._raise_if_cancelled(cancel_callback)
        self._retrieval_index.store_file(source_path, signature, chunks)
        self._raise_if_cancelled(cancel_callback)

    def _finalize_index_scope(
        self,
        current_signatures: Dict[str, FileSignature],
        progress_callback: ProgressCallback,
        cancel_callback: CancelCallback,
    ) -> Dict[str, int]:
        self._raise_if_cancelled(cancel_callback)
        return self._retrieval_index.finalize_scope(
            current_signatures,
            progress_callback,
            cancel_callback,
        )

    def _report_progress_counts(
        self,
        progress_callback: ProgressCallback,
        completed_count: int,
        total_changed: int,
        saved_file_count: int,
        failed_file_count: int,
        stalled_file_count: int,
        last_file_name: str,
        issue_text: str,
    ) -> None:
        self._report(
            progress_callback,
            (
                f"Processed {completed_count}/{total_changed} changed files | "
                f"saved {saved_file_count} | failed {failed_file_count} | "
                f"stalled {stalled_file_count}. Last: {last_file_name}{issue_text}"
            ),
        )

    def _read_and_chunk_document(
        self,
        file_path: Path,
        cancel_callback: CancelCallback = None,
    ) -> List[str]:
        self._raise_if_cancelled(cancel_callback)
        text = self._extract_document_text(file_path, cancel_callback)
        self._raise_if_cancelled(cancel_callback)
        chunks = self._chunker.chunk(text)
        self._raise_if_cancelled(cancel_callback)
        return chunks

    def _extract_document_text(
        self,
        file_path: Path,
        cancel_callback: CancelCallback = None,
    ) -> str:
        if file_path.suffix.lower() == ".pdf":
            return self._extract_pdf_text(file_path, cancel_callback)
        return self._extract_text_file(file_path, cancel_callback)

    def _extract_text_file(
        self,
        file_path: Path,
        cancel_callback: CancelCallback = None,
    ) -> str:
        script = (
            "import pathlib, sys\n"
            "data = pathlib.Path(sys.argv[1]).read_bytes()\n"
            "sys.stdout.buffer.write(data)\n"
        )
        result = self._run_cancellable_subprocess(
            [sys.executable, "-c", script, str(file_path)],
            cancel_callback,
            self._FILE_READ_TIMEOUT_SECONDS,
            "text read",
        )
        if result.returncode != 0:
            error_text = result.stderr.decode("utf-8", errors="replace").strip()
            raise RuntimeError(
                error_text
                or f"text reader exited with code {result.returncode}"
            )
        return result.stdout.decode("utf-8", errors="replace")

    def _extract_pdf_text(
        self,
        file_path: Path,
        cancel_callback: CancelCallback = None,
    ) -> str:
        pdftotext_path = shutil.which("pdftotext")
        pdftotext_error = ""
        if pdftotext_path:
            try:
                result = self._run_cancellable_subprocess(
                    [pdftotext_path, "-layout", str(file_path), "-"],
                    cancel_callback,
                    self._FILE_READ_TIMEOUT_SECONDS,
                    "pdftotext",
                )
                if result.returncode == 0:
                    return result.stdout.decode("utf-8", errors="replace")
                pdftotext_error = (
                    result.stderr.decode("utf-8", errors="replace").strip()
                    or f"pdftotext exited with code {result.returncode}"
                )
            except InterruptedError:
                raise
            except TimeoutError as error:
                pdftotext_error = str(error)

        python_script = (
            "import sys\n"
            "reader_cls = None\n"
            "errors = []\n"
            "try:\n"
            "    from pypdf import PdfReader as reader_cls\n"
            "except Exception as error:\n"
            "    errors.append('pypdf: ' + repr(error))\n"
            "if reader_cls is None:\n"
            "    try:\n"
            "        from PyPDF2 import PdfReader as reader_cls\n"
            "    except Exception as error:\n"
            "        errors.append('PyPDF2: ' + repr(error))\n"
            "if reader_cls is None:\n"
            "    raise RuntimeError('; '.join(errors))\n"
            "reader = reader_cls(sys.argv[1])\n"
            "parts = []\n"
            "for page in reader.pages:\n"
            "    text = page.extract_text() or ''\n"
            "    if text.strip():\n"
            "        parts.append(text)\n"
            "sys.stdout.buffer.write(('\\n\\n'.join(parts)).encode('utf-8', 'replace'))\n"
        )
        try:
            result = self._run_cancellable_subprocess(
                [sys.executable, "-c", python_script, str(file_path)],
                cancel_callback,
                self._FILE_READ_TIMEOUT_SECONDS,
                "Python PDF reader",
            )
        except InterruptedError:
            raise
        except TimeoutError as error:
            raise TimeoutError(
                self._combine_pdf_errors(pdftotext_error, str(error))
            ) from error

        if result.returncode != 0:
            fallback_error = (
                result.stderr.decode("utf-8", errors="replace").strip()
                or f"Python PDF reader exited with code {result.returncode}"
            )
            raise RuntimeError(
                self._combine_pdf_errors(pdftotext_error, fallback_error)
            )
        return result.stdout.decode("utf-8", errors="replace")

    def _run_cancellable_subprocess(
        self,
        command: List[str],
        cancel_callback: CancelCallback,
        timeout_seconds: float,
        operation_name: str,
    ) -> subprocess.CompletedProcess:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        started_at = time.monotonic()

        try:
            while True:
                if cancel_callback is not None and cancel_callback():
                    self._stop_process(process)
                    raise InterruptedError("Index build cancelled.")

                elapsed = time.monotonic() - started_at
                if elapsed >= timeout_seconds:
                    self._stop_process(process)
                    raise TimeoutError(
                        f"{operation_name} exceeded {int(timeout_seconds)} seconds"
                    )

                try:
                    stdout, stderr = process.communicate(
                        timeout=min(
                            self._SUBPROCESS_POLL_SECONDS,
                            max(0.01, timeout_seconds - elapsed),
                        )
                    )
                    return subprocess.CompletedProcess(
                        command,
                        process.returncode,
                        stdout,
                        stderr,
                    )
                except subprocess.TimeoutExpired:
                    continue
        except BaseException:
            if process.poll() is None:
                self._stop_process(process)
            raise

    def _stop_process(self, process: subprocess.Popen) -> None:
        if process.poll() is not None:
            return
        try:
            process.terminate()
            process.wait(timeout=0.50)
        except (OSError, subprocess.TimeoutExpired):
            try:
                process.kill()
                process.wait(timeout=0.50)
            except (OSError, subprocess.TimeoutExpired):
                pass
        try:
            process.communicate(timeout=0.05)
        except (OSError, subprocess.TimeoutExpired):
            pass

    def _combine_pdf_errors(self, first_error: str, second_error: str) -> str:
        if first_error:
            return f"pdftotext: {first_error}; fallback: {second_error}"
        return second_error

    def _short_error(self, error: Exception) -> str:
        text = str(error).strip().replace("\n", " ")
        if not text:
            text = error.__class__.__name__
        if len(text) > 240:
            return text[:237] + "..."
        return text

    def ask(
        self,
        question: str,
        progress_callback: ProgressCallback = None,
        token_callback: TokenCallback = None,
        cancel_callback: CancelCallback = None,
    ) -> Dict[str, object]:
        question = question.strip()
        if not question:
            raise ValueError("Question cannot be empty.")
        if not self._index_ready:
            raise RuntimeError("Build the index before asking a question.")

        self._raise_if_cancelled(cancel_callback, "Question cancelled.")
        hits = self._retrieval_index.search(
            question,
            self._top_k,
            progress_callback,
        )
        self._raise_if_cancelled(cancel_callback, "Question cancelled.")

        context_chunks: List[str] = []
        sources: List[str] = []
        seen_sources = set()
        for _, chunk in hits[: self._max_context_chunks]:
            source_path = chunk["source_path"]
            context_chunks.append(
                f"source_path: {source_path}\n{chunk['text']}"
            )
            if source_path not in seen_sources:
                seen_sources.add(source_path)
                sources.append(source_path)
        if not context_chunks:
            raise RuntimeError("No relevant document context was found.")

        self._report(
            progress_callback,
            "Generating answer with the local LLM...",
        )
        answer = self._language_model.answer(
            question,
            context_chunks,
            token_callback,
            cancel_callback,
        )
        return {"answer": answer, "sources": sources}

    def _normalize_extensions(self, extensions: List[str]) -> Set[str]:
        normalized: Set[str] = set()
        for extension in extensions:
            value = extension.strip().lower()
            if not value:
                continue
            if not value.startswith("."):
                value = "." + value
            normalized.add(value)
        return normalized

    def _report(
        self,
        progress_callback: ProgressCallback,
        message: str,
    ) -> None:
        if progress_callback is not None:
            progress_callback(message)

    def _raise_if_cancelled(
        self,
        cancel_callback: CancelCallback,
        message: str = "Index build cancelled.",
    ) -> None:
        if cancel_callback is not None and cancel_callback():
            raise InterruptedError(message)
