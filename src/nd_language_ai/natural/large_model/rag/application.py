import sys
from pathlib import Path

from PySide6.QtGui import QIcon
from PySide6.QtWidgets import QApplication

from nd_language_ai.natural.large_model.rag.application_config import ApplicationConfig
from nd_language_ai.natural.large_model.rag.rag_settings import RagSettings
from nd_language_ai.natural.large_model.rag.rag_settings_repository import RagSettingsRepository
from nd_language_ai.natural.large_model.rag.service.rag_service_factory import RagServiceFactory
from nd_language_ai.natural.large_model.rag.ui.rag_cancelable_main_window import (
    RagCancelableMainWindow,
)
from nd_language_ai.natural.large_model.rag.ui.rag_style_sheet_builder import RagStyleSheetBuilder


class RagApplication:
    def __init__(self) -> None:
        config = ApplicationConfig()
        default_settings = RagSettings(
            root_folder=str(config.default_root_folder),
            extensions=list(config.default_extensions),
            embedding_model_path=str(config.default_embedding_model_path),
            chat_model_path=str(config.default_chat_model_path),
        )
        settings_repository = RagSettingsRepository(config.settings_path, default_settings)
        settings = settings_repository.load()
        service_factory = RagServiceFactory(config)

        self._qt_application = QApplication(sys.argv)
        self._qt_application.setStyleSheet(RagStyleSheetBuilder().build())

        icon_path = Path(__file__).with_name("run.svg")
        if icon_path.is_file():
            self._qt_application.setWindowIcon(QIcon(str(icon_path)))

        self._main_window = RagCancelableMainWindow(
            service_factory,
            settings_repository,
            settings,
        )

    def run(self) -> int:
        self._main_window.show()
        return self._qt_application.exec()
