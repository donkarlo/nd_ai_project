from pathlib import Path

from ruamel.yaml import YAML
from ruamel.yaml.error import YAMLError

from nd_language_ai.natural.large_model.rag.rag_settings import RagSettings


class RagSettingsRepository:
    def __init__(self, settings_path: Path, default_settings: RagSettings) -> None:
        self._settings_path = Path(settings_path)
        self._default_settings = default_settings

    def load(self) -> RagSettings:
        if not self._settings_path.is_file():
            return self._copy_defaults()

        yaml = YAML(typ="safe")
        try:
            with self._settings_path.open("r", encoding="utf-8") as stream:
                data = yaml.load(stream) or {}
        except (OSError, YAMLError):
            return self._copy_defaults()

        extensions = data.get("extensions", self._default_settings.extensions)
        if not isinstance(extensions, list):
            extensions = self._default_settings.extensions

        return RagSettings(
            root_folder=str(data.get("root_folder", self._default_settings.root_folder)),
            extensions=[str(value) for value in extensions],
            embedding_model_path=str(
                data.get("embedding_model_path", self._default_settings.embedding_model_path)
            ),
            chat_model_path=str(data.get("chat_model_path", self._default_settings.chat_model_path)),
        )

    def save(self, settings: RagSettings) -> None:
        self._settings_path.parent.mkdir(parents=True, exist_ok=True)
        yaml = YAML()
        yaml.default_flow_style = False
        data = {
            "root_folder": settings.root_folder,
            "extensions": list(settings.extensions),
            "embedding_model_path": settings.embedding_model_path,
            "chat_model_path": settings.chat_model_path,
        }
        with self._settings_path.open("w", encoding="utf-8") as stream:
            yaml.dump(data, stream)

    def _copy_defaults(self) -> RagSettings:
        return RagSettings(
            root_folder=self._default_settings.root_folder,
            extensions=list(self._default_settings.extensions),
            embedding_model_path=self._default_settings.embedding_model_path,
            chat_model_path=self._default_settings.chat_model_path,
        )
