import time

from PySide6.QtCore import QObject, Signal, Slot

from nd_language_ai.natural.large_model.rag.service.rag_service import RagService


class AskWorker(QObject):
    progress = Signal(str)
    token = Signal(str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, service: RagService, question: str) -> None:
        super().__init__()
        self._service = service
        self._question = question
        self._cancel_requested = False
        self._started_at = 0.0
        self._generation_started_at = 0.0
        self._first_token_seen = False

    @Slot()
    def run(self) -> None:
        self._started_at = time.perf_counter()
        self._generation_started_at = 0.0
        self._first_token_seen = False
        try:
            result = self._service.ask(
                self._question,
                self._on_progress,
                self._on_token,
                self._is_cancelled,
            )
            total_seconds = time.perf_counter() - self._started_at
            if isinstance(result, dict):
                result = dict(result)
                result["timing_total_seconds"] = total_seconds
                if self._generation_started_at > 0.0:
                    result["timing_generation_seconds"] = (
                        time.perf_counter() - self._generation_started_at
                    )
            self.progress.emit(
                f"Answer complete: total {total_seconds:.2f}s"
            )
            self.finished.emit(result)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))

    @Slot()
    def cancel(self) -> None:
        self._cancel_requested = True

    def _on_progress(self, message: str) -> None:
        if message.startswith("Generating answer with the local LLM"):
            self._generation_started_at = time.perf_counter()
        elapsed = (
            time.perf_counter() - self._started_at
            if self._started_at > 0.0
            else 0.0
        )
        self.progress.emit(f"{message} | total {elapsed:.2f}s")

    def _on_token(self, text: str) -> None:
        if not self._first_token_seen:
            self._first_token_seen = True
            now = time.perf_counter()
            total_seconds = now - self._started_at
            if self._generation_started_at > 0.0:
                generation_seconds = now - self._generation_started_at
                self.progress.emit(
                    (
                        f"First answer token: {total_seconds:.2f}s total | "
                        f"LLM time-to-first-token {generation_seconds:.2f}s"
                    )
                )
            else:
                self.progress.emit(
                    f"First answer token: {total_seconds:.2f}s total"
                )
        self.token.emit(text)

    def _is_cancelled(self) -> bool:
        return self._cancel_requested
