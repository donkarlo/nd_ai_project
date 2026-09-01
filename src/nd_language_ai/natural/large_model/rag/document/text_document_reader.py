from pathlib import Path

from nd_language_ai.natural.large_model.rag.document.document_reader import DocumentReader


class TextDocumentReader(DocumentReader):
    def read(self, file_path: Path) -> str:
        return file_path.read_text(encoding="utf-8", errors="replace")
