from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from nd_language_ai.natural.large_model.rag.rag_settings import RagSettings
from nd_language_ai.natural.large_model.rag.ui.extension_tag_widget import ExtensionTagWidget


class RagSettingsDialog(QDialog):
    BUILD_RESULT = 2

    def __init__(self, settings: RagSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("QA RAG Settings")
        self.setMinimumSize(820, 570)
        self.resize(900, 620)

        self._root_input = QLineEdit(settings.root_folder)
        self._embedding_model_input = QLineEdit(settings.embedding_model_path)
        self._chat_model_input = QLineEdit(settings.chat_model_path)
        self._extension_tags = ExtensionTagWidget(
            settings.extensions if settings.extensions else [".tex", ".pdf"]
        )

        self._browse_root_button = QPushButton("Browse")
        self._browse_root_button.setObjectName("blueButton")
        self._browse_embedding_button = QPushButton("Browse")
        self._browse_embedding_button.setObjectName("blueButton")
        self._browse_chat_button = QPushButton("Browse")
        self._browse_chat_button.setObjectName("blueButton")

        self._cancel_button = QPushButton("Cancel")
        self._cancel_button.setObjectName("secondaryButton")
        self._save_button = QPushButton("Save")
        self._save_button.setObjectName("blueButton")
        self._save_and_build_button = QPushButton("Save & Build Index")
        self._save_and_build_button.setObjectName("greenButton")

        self._build_layout()
        self._connect_signals()

    def settings(self) -> RagSettings:
        return RagSettings(
            root_folder=self._root_input.text().strip(),
            extensions=self._extension_tags.extensions(),
            embedding_model_path=self._embedding_model_input.text().strip(),
            chat_model_path=self._chat_model_input.text().strip(),
        )

    def _build_layout(self) -> None:
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(24, 22, 24, 24)
        root_layout.setSpacing(16)

        title = QLabel("RAG settings")
        title.setObjectName("titleLabel")
        subtitle = QLabel(
            "Choose the document scope, file types, embedding model, and local LLM."
        )
        subtitle.setObjectName("subtitleLabel")
        root_layout.addWidget(title)
        root_layout.addWidget(subtitle)

        card = QFrame()
        card.setObjectName("card")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(18, 18, 18, 18)
        card_layout.setSpacing(10)

        card_layout.addWidget(self._field_label("Root folder"))
        root_row = QHBoxLayout()
        root_row.setSpacing(8)
        root_row.addWidget(self._root_input, 1)
        root_row.addWidget(self._browse_root_button)
        card_layout.addLayout(root_row)

        card_layout.addWidget(self._field_label("File extensions"))
        card_layout.addWidget(self._extension_tags)

        models_title = QLabel("Local models")
        models_title.setObjectName("sectionTitle")
        card_layout.addSpacing(4)
        card_layout.addWidget(models_title)

        card_layout.addWidget(self._field_label("Embedding model"))
        embedding_row = QHBoxLayout()
        embedding_row.setSpacing(8)
        embedding_row.addWidget(self._embedding_model_input, 1)
        embedding_row.addWidget(self._browse_embedding_button)
        card_layout.addLayout(embedding_row)

        card_layout.addWidget(self._field_label("LLM model"))
        chat_row = QHBoxLayout()
        chat_row.setSpacing(8)
        chat_row.addWidget(self._chat_model_input, 1)
        chat_row.addWidget(self._browse_chat_button)
        card_layout.addLayout(chat_row)

        root_layout.addWidget(card)

        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self._cancel_button)
        button_row.addWidget(self._save_button)
        button_row.addWidget(self._save_and_build_button)
        root_layout.addLayout(button_row)

    def _connect_signals(self) -> None:
        self._browse_root_button.clicked.connect(self._browse_root_folder)
        self._browse_embedding_button.clicked.connect(self._browse_embedding_model)
        self._browse_chat_button.clicked.connect(self._browse_chat_model)
        self._cancel_button.clicked.connect(self.reject)
        self._save_button.clicked.connect(self._save)
        self._save_and_build_button.clicked.connect(self._save_and_build)

    def _field_label(self, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def _browse_root_folder(self) -> None:
        current_path = Path(self._root_input.text().strip()).expanduser()
        start_directory = str(current_path if current_path.is_dir() else Path.home())
        selected_folder = QFileDialog.getExistingDirectory(
            self,
            "Select document root folder",
            start_directory,
        )
        if selected_folder:
            self._root_input.setText(selected_folder)

    def _browse_embedding_model(self) -> None:
        self._browse_model_file(
            self._embedding_model_input,
            "Select embedding GGUF model",
        )

    def _browse_chat_model(self) -> None:
        self._browse_model_file(
            self._chat_model_input,
            "Select LLM GGUF model",
        )

    def _browse_model_file(self, target_input: QLineEdit, title: str) -> None:
        current_path = Path(target_input.text().strip()).expanduser()
        if current_path.is_file():
            start_directory = str(current_path.parent)
        elif current_path.parent.is_dir():
            start_directory = str(current_path.parent)
        else:
            start_directory = str(Path.home())

        selected_file, _ = QFileDialog.getOpenFileName(
            self,
            title,
            start_directory,
            "GGUF models (*.gguf);;All files (*)",
        )
        if selected_file:
            target_input.setText(selected_file)

    def _save(self) -> None:
        if not self._validate():
            return
        self.accept()

    def _save_and_build(self) -> None:
        if not self._validate():
            return
        self.done(self.BUILD_RESULT)

    def _validate(self) -> bool:
        settings = self.settings()
        if not settings.root_folder:
            QMessageBox.warning(self, "Missing root folder", "Choose a root folder first.")
            return False
        if not Path(settings.root_folder).expanduser().is_dir():
            QMessageBox.warning(
                self,
                "Invalid root folder",
                f"Folder not found:\n{settings.root_folder}",
            )
            return False
        if not settings.extensions:
            QMessageBox.warning(
                self,
                "Missing extensions",
                "Add at least one file extension.",
            )
            return False
        if not settings.embedding_model_path:
            QMessageBox.warning(
                self,
                "Missing embedding model",
                "Choose an embedding model first.",
            )
            return False
        if not Path(settings.embedding_model_path).expanduser().is_file():
            QMessageBox.warning(
                self,
                "Embedding model not found",
                f"Embedding model not found:\n{settings.embedding_model_path}",
            )
            return False
        if not settings.chat_model_path:
            QMessageBox.warning(
                self,
                "Missing LLM model",
                "Choose an LLM model first.",
            )
            return False
        if not Path(settings.chat_model_path).expanduser().is_file():
            QMessageBox.warning(
                self,
                "LLM model not found",
                f"LLM model not found:\n{settings.chat_model_path}",
            )
            return False
        return True
