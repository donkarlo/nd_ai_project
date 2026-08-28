from typing import List


class Chunker:
    def __init__(self, chunk_size_chars: int, chunk_overlap_chars: int):
        self._chunk_size_chars = int(chunk_size_chars)
        self._chunk_overlap_chars = int(chunk_overlap_chars)

        if self._chunk_size_chars <= 0:
            raise ValueError("chunk_size_chars must be > 0")

        if self._chunk_overlap_chars < 0:
            raise ValueError("chunk_overlap_chars must be >= 0")

        if self._chunk_overlap_chars >= self._chunk_size_chars:
            raise ValueError("chunk_overlap_chars must be < chunk_size_chars")

    def chunk(self, text: str) -> List[str]:
        normalized_text = text.replace("\r\n", "\n").replace("\r", "\n")
        if not normalized_text.strip():
            return []

        chunks: List[str] = []
        start_index = 0
        text_length = len(normalized_text)

        while start_index < text_length:
            end_index = start_index + self._chunk_size_chars
            if end_index > text_length:
                end_index = text_length

            chunk_text = normalized_text[start_index:end_index].strip()
            if chunk_text:
                chunks.append(chunk_text)

            if end_index >= text_length:
                break

            start_index = end_index - self._chunk_overlap_chars

        return chunks
