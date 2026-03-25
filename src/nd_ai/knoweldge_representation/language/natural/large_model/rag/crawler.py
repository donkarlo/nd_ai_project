from pathlib import Path
from typing import Iterable, List, Tuple


class Crawler:
    def __init__(self, repo_roots: List[str], allowed_extensions: List[str], ignored_directories: List[str]):
        self._repo_roots = [Path(p) for p in repo_roots]
        self._allowed_extensions = set([e.lower() for e in allowed_extensions])
        self._ignored_directories = set(ignored_directories)

    def iter_files(self) -> Iterable[Path]:
        for root in self._repo_roots:
            if not root.exists() or not root.is_dir():
                continue

            for path in root.rglob("*"):
                if path.is_dir():
                    continue

                if path.suffix.lower() not in self._allowed_extensions:
                    continue

                if any(part in self._ignored_directories for part in path.parts):
                    continue

                yield path

    def read_text(self, file_path: Path) -> str:
        try:
            return file_path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return ""

    def load_documents(self) -> List[Tuple[str, str]]:
        documents: List[Tuple[str, str]] = []
        for file_path in self.iter_files():
            text = self.read_text(file_path)
            if not text.strip():
                continue
            documents.append((str(file_path), text))
        return documents
