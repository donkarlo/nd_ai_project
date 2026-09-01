from pathlib import Path
from typing import Optional

from PySide6.QtCore import Qt, QThread
from PySide6.QtGui import QCloseEvent, QTextCursor
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from nd_language_ai.natural.large_model.rag.rag_settings import RagSettings
from nd_language_ai.natural.large_model.rag.rag_settings_repository import RagSettingsRepository
from nd_language_ai.natural.large_model.rag.service.rag_service import RagService
from nd_language_ai.natural.large_model.rag.service.rag_service_factory import RagServiceFactory
from nd_language_ai.natural.large_model.rag.ui.ask_worker import AskWorker
from nd_language_ai.natural.large_model.rag.ui.index_worker import IndexWorker
from nd_language_ai.natural.large_model.rag.ui.rag_settings_dialog import RagSettingsDialog


class RagMainWindow(QMainWindow):
    def __init__(
        self,
        service_factory: RagServiceFactory,
        settings_repository: RagSettingsRepository,
        settings: RagSettings,
    ) -> None:
        super().__init__()
        self._service_factory = service_factory
        self._settings_repository = settings_repository
        self._settings = self._copy_settings(settings)
        self._service: Optional[RagService] = None
        self._index_ready = False
        self._pending_question = ""
        self._index_thread: Optional[QThread] = None
        self._index_worker: Optional[IndexWorker] = None
        self._ask_thread: Optional[QThread] = None
        self._ask_worker: Optional[AskWorker] = None
        self._closing = False

        self.setWindowTitle("QA RAG")
        self.setMinimumSize(900, 700)
        self.resize(1050, 860)

        self._settings_button = QPushButton("Settings")
        self._settings_button.setObjectName("secondaryButton")

        self._status_label = QLabel()
        self._status_label.setWordWrap(True)
        self._set_status(
            "Ready. Open Settings to change the document scope or local models.",
            "idle",
        )

        self._question_input = QPlainTextEdit()
        self._question_input.setPlaceholderText(
            "Ask a question about the selected documents..."
        )
        self._question_input.setMinimumHeight(125)
        self._question_input.setMaximumHeight(180)

        self._ask_button = QPushButton("Ask")
        self._ask_button.setObjectName("peachButton")

        self._answer_output = QPlainTextEdit()
        self._answer_output.setReadOnly(True)
        self._answer_output.setPlaceholderText("The answer will appear here.")
        self._answer_output.setMinimumHeight(190)

        self._sources_list = QListWidget()
        self._sources_list.setMinimumHeight(120)
        self._sources_list.setWordWrap(True)
        self._sources_list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self._build_layout()
        self._connect_signals()

    def _build_layout(self) -> None:
        page = QWidget()
        page_layout = QVBoxLayout(page)
        page_layout.setContentsMargins(26, 22, 26, 28)
        page_layout.setSpacing(17)

        header_layout = QHBoxLayout()
        header_text_layout = QVBoxLayout()
        header_text_layout.setSpacing(2)

        title = QLabel("QA RAG")
        title.setObjectName("titleLabel")
        subtitle = QLabel(
            "Search your local documents with retrieval-augmented question answering"
        )
        subtitle.setObjectName("subtitleLabel")
        header_text_layout.addWidget(title)
        header_text_layout.addWidget(subtitle)

        header_layout.addLayout(header_text_layout, 1)
        header_layout.addWidget(self._settings_button)
        page_layout.addLayout(header_layout)
        page_layout.addWidget(self._status_label)

        question_card = QFrame()
        question_card.setObjectName("card")
        question_layout = QVBoxLayout(question_card)
        question_layout.setContentsMargins(18, 16, 18, 18)
        question_layout.setSpacing(10)

        question_title = QLabel("Ask your documents")
        question_title.setObjectName("sectionTitle")
        question_layout.addWidget(question_title)
        question_layout.addWidget(self._question_input)

        ask_layout = QHBoxLayout()
        ask_layout.addStretch(1)
        ask_layout.addWidget(self._ask_button)
        question_layout.addLayout(ask_layout)
        page_layout.addWidget(question_card)

        answer_card = QFrame()
        answer_card.setObjectName("card")
        answer_layout = QVBoxLayout(answer_card)
        answer_layout.setContentsMargins(18, 16, 18, 18)
        answer_layout.setSpacing(10)

        answer_title = QLabel("Answer")
        answer_title.setObjectName("sectionTitle")
        answer_layout.addWidget(answer_title)
        answer_layout.addWidget(self._answer_output)

        sources_title = QLabel("Sources")
        sources_title.setObjectName("fieldLabel")
        answer_layout.addWidget(sources_title)
        answer_layout.addWidget(self._sources_list)
        page_layout.addWidget(answer_card)
        page_layout.addStretch(1)

        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(page)
        self.setCentralWidget(scroll_area)

    def _connect_signals(self) -> None:
        self._settings_button.clicked.connect(self._open_settings)
        self._ask_button.clicked.connect(self._start_ask)

    def _open_settings(self) -> None:
        if self._index_thread is not None or self._ask_thread is not None or self._closing:
            return

        dialog = RagSettingsDialog(self._settings, self)
        result = dialog.exec()
        if result == int(RagSettingsDialog.DialogCode.Rejected):
            return

        settings = dialog.settings()
        if not self._apply_settings(settings):
            return

        if result == RagSettingsDialog.BUILD_RESULT:
            self._start_index_build()

    def _apply_settings(self, settings: RagSettings) -> bool:
        changed = not self._settings_equal(self._settings, settings)
        try:
            self._settings_repository.save(settings)
        except OSError as error:
            QMessageBox.critical(
                self,
                "Settings error",
                f"Could not save settings:\n{error}",
            )
            return False

        self._settings = self._copy_settings(settings)
        if changed:
            self._service = None
            self._index_ready = False
            self._set_status(
                "Settings saved. The next Ask will rebuild the index automatically.",
                "warning",
            )
        else:
            self._set_status("Settings saved.", "ready")
        return True

    def _start_index_build(self) -> None:
        if self._index_thread is not None or self._closing:
            return
        if not self._validate_runtime_settings():
            return

        self._service = self._service_factory.create(
            self._settings.embedding_model_path,
            self._settings.chat_model_path,
        )
        self._index_ready = False
        self._answer_output.clear()
        self._sources_list.clear()

        extension_text = ", ".join(sorted(self._settings.extensions))
        self._set_status(
            f"Building fast index. Only these extensions are included: {extension_text}",
            "busy",
        )
        self._set_controls_enabled(False)

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

    def _on_index_progress(self, message: str) -> None:
        self._set_status(message, "busy")

    def _on_index_built(self, result: object) -> None:
        data = dict(result)
        self._index_ready = True
        self._set_controls_enabled(True)

        skipped_count = len(data.get("skipped_files", []))
        extension_text = ", ".join(data.get("extensions", []))
        self._set_status(
            (
                f"Index ready: {data['file_count']} readable files, "
                f"{data['chunk_count']} chunks, {skipped_count} skipped. "
                f"Extensions: {extension_text}."
            ),
            "ready",
        )

        pending_question = self._pending_question.strip()
        self._pending_question = ""
        if pending_question and not self._closing:
            self._run_question(pending_question)

    def _on_index_failed(self, message: str) -> None:
        self._index_ready = False
        self._pending_question = ""
        self._set_controls_enabled(True)
        self._set_status(
            "Index build failed. Open Settings or try again.",
            "error",
        )
        if not self._closing:
            QMessageBox.critical(self, "Index error", message)

    def _on_index_cancelled(self) -> None:
        self._index_ready = False
        self._pending_question = ""
        if not self._closing:
            self._set_controls_enabled(True)
            self._set_status("Index build cancelled.", "warning")

    def _on_index_thread_finished(self) -> None:
        self._index_worker = None
        self._index_thread = None
        self._finish_close_if_idle()

    def _start_ask(self) -> None:
        if self._ask_thread is not None or self._index_thread is not None or self._closing:
            return

        question = self._question_input.toPlainText().strip()
        if not question:
            QMessageBox.warning(self, "Missing question", "Enter a question first.")
            return

        if not self._index_ready:
            self._pending_question = question
            self._start_index_build()
            return

        self._run_question(question)

    def _run_question(self, question: str) -> None:
        if self._service is None:
            self._pending_question = question
            self._start_index_build()
            return

        self._set_controls_enabled(False)
        self._answer_output.clear()
        self._sources_list.clear()
        self._set_status("Searching the index...", "busy")

        self._ask_thread = QThread(self)
        self._ask_worker = AskWorker(self._service, question)
        self._ask_worker.moveToThread(self._ask_thread)
        self._ask_thread.started.connect(self._ask_worker.run)
        self._ask_worker.progress.connect(self._on_ask_progress)
        self._ask_worker.token.connect(self._on_answer_token)
        self._ask_worker.finished.connect(self._on_answer_ready)
        self._ask_worker.failed.connect(self._on_ask_failed)
        self._ask_worker.cancelled.connect(self._on_ask_cancelled)
        self._ask_worker.finished.connect(self._ask_thread.quit)
        self._ask_worker.failed.connect(self._ask_thread.quit)
        self._ask_worker.cancelled.connect(self._ask_thread.quit)
        self._ask_worker.finished.connect(self._ask_worker.deleteLater)
        self._ask_worker.failed.connect(self._ask_worker.deleteLater)
        self._ask_worker.cancelled.connect(self._ask_worker.deleteLater)
        self._ask_thread.finished.connect(self._on_ask_thread_finished)
        self._ask_thread.finished.connect(self._ask_thread.deleteLater)
        self._ask_thread.start()

    def _on_ask_progress(self, message: str) -> None:
        self._set_status(message, "busy")

    def _on_answer_token(self, token: str) -> None:
        if not token:
            return
        cursor = self._answer_output.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(token)
        self._answer_output.setTextCursor(cursor)
        self._answer_output.ensureCursorVisible()

    def _on_answer_ready(self, result: object) -> None:
        data = dict(result)
        final_answer = str(data.get("answer", "")).strip()
        if final_answer:
            self._answer_output.setPlainText(final_answer)

        self._sources_list.clear()
        for source_path in data.get("sources", []):
            item = QListWidgetItem(str(source_path))
            item.setToolTip(str(source_path))
            self._sources_list.addItem(item)

        self._set_controls_enabled(True)
        self._set_status("Answer ready.", "ready")

    def _on_ask_failed(self, message: str) -> None:
        self._answer_output.clear()
        self._set_controls_enabled(True)
        self._set_status("Question failed. You can try again.", "error")
        if not self._closing:
            QMessageBox.critical(self, "Question error", message)

    def _on_ask_cancelled(self) -> None:
        if not self._closing:
            self._set_controls_enabled(True)
            self._set_status("Question cancelled.", "warning")

    def _on_ask_thread_finished(self) -> None:
        self._ask_worker = None
        self._ask_thread = None
        self._finish_close_if_idle()

    def _validate_runtime_settings(self) -> bool:
        root_folder = self._settings.root_folder
        embedding_model_path = self._settings.embedding_model_path
        chat_model_path = self._settings.chat_model_path

        if not root_folder or not Path(root_folder).expanduser().is_dir():
            QMessageBox.warning(
                self,
                "Invalid root folder",
                "Open Settings and choose a valid root folder.",
            )
            return False
        if not self._settings.extensions:
            QMessageBox.warning(
                self,
                "Missing extensions",
                "Open Settings and add at least one file extension.",
            )
            return False
        if not embedding_model_path or not Path(embedding_model_path).expanduser().is_file():
            QMessageBox.warning(
                self,
                "Embedding model not found",
                "Open Settings and choose a valid embedding model.",
            )
            return False
        if not chat_model_path or not Path(chat_model_path).expanduser().is_file():
            QMessageBox.warning(
                self,
                "LLM model not found",
                "Open Settings and choose a valid LLM model.",
            )
            return False
        return True

    def _set_controls_enabled(self, enabled: bool) -> None:
        self._settings_button.setEnabled(enabled)
        self._ask_button.setEnabled(enabled)
        self._question_input.setEnabled(enabled)

    def _settings_equal(self, left: RagSettings, right: RagSettings) -> bool:
        return (
            left.root_folder == right.root_folder
            and list(left.extensions) == list(right.extensions)
            and left.embedding_model_path == right.embedding_model_path
            and left.chat_model_path == right.chat_model_path
        )

    def _copy_settings(self, settings: RagSettings) -> RagSettings:
        return RagSettings(
            root_folder=settings.root_folder,
            extensions=list(settings.extensions),
            embedding_model_path=settings.embedding_model_path,
            chat_model_path=settings.chat_model_path,
        )

    def _set_status(self, text: str, state: str) -> None:
        styles = {
            "idle": "background: #f7f7f5; color: #555555; border: 1px solid #ddddda;",
            "busy": "background: #fff2d9; color: #805419; border: 1px solid #edcc91;",
            "ready": "background: #e9f4e6; color: #41633c; border: 1px solid #bfd6ba;",
            "warning": "background: #fff0dc; color: #8a5b22; border: 1px solid #e7c08d;",
            "error": "background: #fbe7e4; color: #933b31; border: 1px solid #e6aaa3;",
        }
        self._status_label.setText(text)
        self._status_label.setStyleSheet(
            styles.get(state, styles["idle"])
            + " border-radius: 9px; padding: 8px 10px; font-weight: 650;"
        )

    def closeEvent(self, event: QCloseEvent) -> None:
        try:
            self._settings_repository.save(self._settings)
        except OSError:
            pass

        if self._index_thread is None and self._ask_thread is None:
            event.accept()
            return

        self._closing = True
        self._pending_question = ""
        self._set_status("Stopping the current task before closing...", "warning")
        self._set_controls_enabled(False)

        if self._index_worker is not None:
            self._index_worker.cancel()
        if self._ask_worker is not None:
            self._ask_worker.cancel()
        event.ignore()

    def _finish_close_if_idle(self) -> None:
        if self._closing and self._index_thread is None and self._ask_thread is None:
            self.close()
