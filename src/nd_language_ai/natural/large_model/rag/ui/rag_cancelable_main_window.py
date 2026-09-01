from PySide6.QtCore import QThread, QTimer
from PySide6.QtWidgets import QHBoxLayout, QMessageBox, QPushButton

from nd_language_ai.natural.large_model.rag.rag_settings import RagSettings
from nd_language_ai.natural.large_model.rag.rag_settings_repository import RagSettingsRepository
from nd_language_ai.natural.large_model.rag.service.persistent_rag_service import (
    PersistentRagService,
)
from nd_language_ai.natural.large_model.rag.service.rag_service_factory import RagServiceFactory
from nd_language_ai.natural.large_model.rag.ui.index_worker import IndexWorker
from nd_language_ai.natural.large_model.rag.ui.rag_main_window import RagMainWindow


class RagCancelableMainWindow(RagMainWindow):
    def __init__(
        self,
        service_factory: RagServiceFactory,
        settings_repository: RagSettingsRepository,
        settings: RagSettings,
    ) -> None:
        super().__init__(service_factory, settings_repository, settings)

        self._build_index_button = QPushButton("Build / Update Index")
        self._build_index_button.setObjectName("secondaryButton")
        self._build_index_button.clicked.connect(self._start_index_build)

        self._cancel_index_button = QPushButton("Cancel Indexing")
        self._cancel_index_button.setObjectName("secondaryButton")
        self._cancel_index_button.setVisible(False)
        self._cancel_index_button.clicked.connect(self._cancel_index_build)

        button_layout = QHBoxLayout()
        button_layout.addStretch(1)
        button_layout.addWidget(self._build_index_button)
        button_layout.addWidget(self._cancel_index_button)

        page = self.centralWidget().widget()
        page.layout().insertLayout(2, button_layout)

        QTimer.singleShot(50, self._initialize_cached_index)

    def _initialize_cached_index(self) -> None:
        if self._closing:
            return

        summary = self._inspect_cached_index()
        self._index_ready = bool(summary.get("usable", False))
        self._set_controls_enabled(True)

        if self._index_ready:
            self._set_status(
                (
                    f"Cached index ready: {summary['file_count']} files, "
                    f"{summary['chunk_count']} chunks. No scan is running. "
                    "Use Build / Update Index only when you want to refresh it."
                ),
                "ready",
            )
            return

        cleanup_text = (
            " Obsolete or incomplete cache was removed."
            if summary.get("cleanup_performed")
            else ""
        )
        self._set_status(
            (
                "No usable index is available. No scan is running. "
                "Click Build / Update Index when you want to create it."
                + cleanup_text
            ),
            "warning",
        )

    def _inspect_cached_index(self) -> dict:
        return dict(
            PersistentRagService.inspect_cached_scope(
                self._settings.root_folder,
                self._settings.extensions,
                delete_unusable=True,
            )
        )

    def _ensure_service(self) -> bool:
        if self._service is not None:
            return True
        try:
            self._service = self._service_factory.create(
                self._settings.embedding_model_path,
                self._settings.chat_model_path,
            )
            return True
        except Exception as error:
            self._set_status("Could not initialize the local RAG models.", "error")
            if not self._closing:
                QMessageBox.critical(self, "RAG initialization error", str(error))
            return False

    def _use_cached_index(self) -> dict:
        if not isinstance(self._service, PersistentRagService):
            return {"usable": False, "file_count": 0, "chunk_count": 0}
        return dict(
            self._service.use_cached_index(
                self._settings.root_folder,
                self._settings.extensions,
            )
        )

    def _apply_settings(self, settings: RagSettings) -> bool:
        changed = not self._settings_equal(self._settings, settings)
        if not super()._apply_settings(settings):
            return False

        if changed:
            summary = self._inspect_cached_index()
            self._index_ready = bool(summary.get("usable", False))
            if self._index_ready:
                self._set_status(
                    (
                        f"Settings saved. Cached index ready: {summary['file_count']} files, "
                        f"{summary['chunk_count']} chunks. No scan was started."
                    ),
                    "ready",
                )
            else:
                self._set_status(
                    (
                        "Settings saved. No index was built automatically. "
                        "Click Build / Update Index when you want to refresh this scope."
                    ),
                    "warning",
                )
        else:
            self._set_status("Settings saved. No scan was started.", "ready")
        return True

    def _start_index_build(self) -> None:
        if self._index_thread is not None or self._closing:
            return
        if not self._validate_runtime_settings():
            return

        summary = self._inspect_cached_index()
        had_cache = bool(summary.get("usable", False))
        self._index_ready = had_cache

        if not self._ensure_service():
            return

        if had_cache:
            service_summary = self._use_cached_index()
            had_cache = bool(service_summary.get("usable", False))
            self._index_ready = had_cache

        if not had_cache and isinstance(self._service, PersistentRagService):
            try:
                self._service.reset_index_cache()
            except OSError as error:
                QMessageBox.critical(
                    self,
                    "Index cache error",
                    f"Could not replace the old index cache:\n{error}",
                )
                return

        if had_cache:
            self._set_status(
                "Updating the existing index because you requested it. The cached index remains usable.",
                "busy",
            )
        else:
            self._answer_output.clear()
            self._sources_list.clear()
            self._set_status(
                "Building the index because you requested it. No automatic scan will run on startup.",
                "busy",
            )

        self._settings_button.setEnabled(False)
        self._build_index_button.setEnabled(False)
        self._question_input.setEnabled(True)
        self._ask_button.setEnabled(True)
        self._cancel_index_button.setEnabled(True)
        self._cancel_index_button.setVisible(True)

        self._index_thread = QThread(self)
        self._index_worker = IndexWorker(
            self._service,
            self._settings.root_folder,
            self._settings.extensions,
        )
        self._index_worker.moveToThread(self._index_thread)
        self._index_thread.started.connect(self._index_worker.run)
        self._index_worker.progress.connect(self._on_index_progress)
        self._index_worker.finished.connect(self._on_index_built)
        self._index_worker.failed.connect(self._on_index_failed)
        self._index_worker.cancelled.connect(self._on_index_cancelled)
        self._index_worker.finished.connect(self._index_thread.quit)
        self._index_worker.failed.connect(self._index_thread.quit)
        self._index_worker.cancelled.connect(self._index_thread.quit)
        self._index_worker.finished.connect(self._index_worker.deleteLater)
        self._index_worker.failed.connect(self._index_worker.deleteLater)
        self._index_worker.cancelled.connect(self._index_worker.deleteLater)
        self._index_thread.finished.connect(self._on_index_thread_finished)
        self._index_thread.finished.connect(self._index_thread.deleteLater)
        self._index_thread.start()

    def _start_ask(self) -> None:
        if self._closing or self._ask_thread is not None:
            return

        question = self._question_input.toPlainText().strip()
        if not question:
            QMessageBox.warning(self, "Missing question", "Enter a question first.")
            return

        if not self._index_ready:
            if self._index_thread is not None:
                self._pending_question = question
                self._set_status(
                    "Question queued until the index build you started becomes usable.",
                    "busy",
                )
            else:
                self._set_status(
                    (
                        "No usable index is available. Ask does not start indexing automatically. "
                        "Click Build / Update Index first."
                    ),
                    "warning",
                )
            return

        if not self._ensure_service():
            return

        summary = self._use_cached_index()
        if not summary.get("usable"):
            self._index_ready = False
            self._set_status(
                "The cached index is no longer usable. Click Build / Update Index to replace it.",
                "warning",
            )
            return

        self._run_question(question)

    def _cancel_index_build(self) -> None:
        if self._index_worker is None:
            return
        self._cancel_index_button.setEnabled(False)
        self._set_status("Cancelling the index operation...", "busy")
        self._index_worker.cancel()

    def _on_index_progress(self, message: str) -> None:
        self._set_status(message, "busy")
        self._settings_button.setEnabled(False)
        self._build_index_button.setEnabled(False)
        self._question_input.setEnabled(True)
        self._ask_button.setEnabled(True)

    def _on_index_built(self, result: object) -> None:
        self._cancel_index_button.setVisible(False)
        self._build_index_button.setEnabled(True)
        super()._on_index_built(result)

        if self._ask_thread is not None:
            return

        data = dict(result)
        failed_count = int(data.get("failed_file_count", 0))
        stalled_count = int(data.get("stalled_file_count", 0))
        updated_count = int(data.get("updated_file_count", 0))

        if updated_count == 0 and failed_count == 0 and stalled_count == 0:
            self._set_status(
                (
                    f"Index is already up to date: {data['file_count']} files, "
                    f"{data['chunk_count']} chunks. No files were re-indexed."
                ),
                "ready",
            )
        elif failed_count or stalled_count:
            self._set_status(
                (
                    f"Index ready: {data['file_count']} files, {data['chunk_count']} chunks | "
                    f"updated {updated_count} | failed {failed_count} | stalled {stalled_count}."
                ),
                "warning",
            )

    def _on_index_failed(self, message: str) -> None:
        self._cancel_index_button.setVisible(False)
        self._build_index_button.setEnabled(True)
        if self._index_ready:
            self._settings_button.setEnabled(True)
            self._question_input.setEnabled(True)
            self._ask_button.setEnabled(True)
            self._set_status(
                "Index update failed, but the previous cached index is still usable.",
                "warning",
            )
            return
        super()._on_index_failed(message)

    def _on_index_cancelled(self) -> None:
        self._cancel_index_button.setVisible(False)
        self._build_index_button.setEnabled(True)
        if self._index_ready:
            self._settings_button.setEnabled(True)
            self._question_input.setEnabled(True)
            self._ask_button.setEnabled(True)
            self._set_status(
                "Index update cancelled. The previous cached index is still usable.",
                "warning",
            )
            return
        super()._on_index_cancelled()

    def _on_index_thread_finished(self) -> None:
        self._cancel_index_button.setVisible(False)
        self._build_index_button.setEnabled(self._ask_thread is None)
        super()._on_index_thread_finished()

    def _set_controls_enabled(self, enabled: bool) -> None:
        super()._set_controls_enabled(enabled)
        if hasattr(self, "_build_index_button"):
            self._build_index_button.setEnabled(
                enabled
                and self._index_thread is None
                and self._ask_thread is None
            )
