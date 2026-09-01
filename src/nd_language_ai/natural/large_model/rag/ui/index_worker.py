from threading import Event
from typing import List

from PySide6.QtCore import QObject, Signal, Slot

from nd_language_ai.natural.large_model.rag.service.rag_service import RagService


class IndexWorker(QObject):
    progress = Signal(str)
    finished = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(
        self,
        service: RagService,
        root_folder: str,
        extensions: List[str],
    ) -> None:
        super().__init__()
        self._service = service
        self._root_folder = root_folder
        self._extensions = list(extensions)
        self._cancel_event = Event()

    def cancel(self) -> None:
        self._cancel_event.set()

    @Slot()
    def run(self) -> None:
        try:
            result = self._service.build_index(
                self._root_folder,
                self._extensions,
                self.progress.emit,
                self._cancel_event.is_set,
            )
            self.finished.emit(result)
        except InterruptedError:
            self.cancelled.emit()
        except Exception as error:
            self.failed.emit(str(error))
