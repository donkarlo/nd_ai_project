from typing import List


class Chunker:
    def __init__(self, chunk_size_chars: int, chunk_overlap_chars: int) -> None:
        if chunk_size_chars <= 0:
            raise ValueError("chunk_size_chars must be greater than zero")
        if chunk_overlap_chars < 0 or chunk_overlap_chars >= chunk_size_chars:
            raise ValueError("chunk_overlap_chars must be between zero and chunk_size_chars")
        self._chunk_size_chars = chunk_size_chars
        self._chunk_overlap_chars = chunk_overlap_chars

    def chunk(self, text: str) -> List[str]:
        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
        if not normalized_text:
            return []
        chunks: List[str] = []
        start_index = 0
        while start_index < len(normalized_text):
            end_index = min(start_index + self._chunk_size_chars, len(normalized_text))
            chunk_text = normalized_text[start_index:end_index].strip()
            if chunk_text:
                chunks.append(chunk_text)
            if end_index >= len(normalized_text):
                break
            start_index = end_index - self._chunk_overlap_chars
        return chunks
