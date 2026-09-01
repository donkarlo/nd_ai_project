import os
from pathlib import Path
from typing import Iterable, Set


class FileCrawler:
    def __init__(self, ignored_directories: Set[str]) -> None:
        self._ignored_directories = set(ignored_directories)

    def iter_files(
        self,
        root_folder: Path,
        allowed_extensions: Set[str],
    ) -> Iterable[Path]:
        normalized_extensions = {
            extension.lower()
            for extension in allowed_extensions
            if extension
        }

        for current_root, directory_names, file_names in os.walk(root_folder):
            directory_names[:] = [
                directory_name
                for directory_name in directory_names
                if directory_name not in self._ignored_directories
            ]

            current_path = Path(current_root)
            for file_name in file_names:
                file_path = current_path / file_name
                if file_path.suffix.lower() not in normalized_extensions:
                    continue
                yield file_path
