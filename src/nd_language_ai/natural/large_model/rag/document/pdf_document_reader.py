from pathlib import Path

from nd_language_ai.natural.large_model.rag.document.document_reader import DocumentReader


class PdfDocumentReader(DocumentReader):
    def read(self, file_path: Path) -> str:
        from pypdf import PdfReader

        reader = PdfReader(str(file_path))
        pages = []
        for page in reader.pages:
            text = page.extract_text() or ""
            if text.strip():
                pages.append(text)
        return "\n\n".join(pages)
