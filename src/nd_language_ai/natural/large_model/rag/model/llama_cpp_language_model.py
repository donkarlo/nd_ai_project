from pathlib import Path
from typing import List, Optional

from nd_language_ai.natural.large_model.rag.model.language_model import (
    CancelCallback,
    LanguageModel,
    TokenCallback,
)


class _ThinkingTextFilter:
    _open_tag = "<think>"
    _close_tag = "</think>"

    def __init__(self) -> None:
        self._buffer = ""
        self._inside_thinking = False

    def feed(self, text: str) -> str:
        if not text:
            return ""

        self._buffer += text
        visible_parts: List[str] = []

        while self._buffer:
            if self._inside_thinking:
                close_index = self._buffer.find(self._close_tag)
                if close_index >= 0:
                    self._buffer = self._buffer[
                        close_index + len(self._close_tag) :
                    ]
                    self._inside_thinking = False
                    continue

                keep_count = self._possible_tag_prefix_length(
                    self._buffer,
                    self._close_tag,
                )
                self._buffer = (
                    self._buffer[-keep_count:] if keep_count else ""
                )
                break

            open_index = self._buffer.find(self._open_tag)
            if open_index >= 0:
                visible_parts.append(self._buffer[:open_index])
                self._buffer = self._buffer[
                    open_index + len(self._open_tag) :
                ]
                self._inside_thinking = True
                continue

            keep_count = self._possible_tag_prefix_length(
                self._buffer,
                self._open_tag,
            )
            if keep_count:
                visible_parts.append(self._buffer[:-keep_count])
                self._buffer = self._buffer[-keep_count:]
            else:
                visible_parts.append(self._buffer)
                self._buffer = ""
            break

        return "".join(visible_parts)

    def finish(self) -> str:
        if self._inside_thinking:
            self._buffer = ""
            return ""
        remaining = self._buffer
        self._buffer = ""
        return remaining

    def _possible_tag_prefix_length(self, text: str, tag: str) -> int:
        maximum = min(len(text), len(tag) - 1)
        for length in range(maximum, 0, -1):
            if text.endswith(tag[:length]):
                return length
        return 0


class LlamaCppLanguageModel(LanguageModel):
    def __init__(
        self,
        model_path: Path,
        context_size: int,
        max_tokens: int,
        temperature: float,
        top_p: float,
        repeat_penalty: float,
        n_threads: int,
    ) -> None:
        self._model_path = Path(model_path)
        self._context_size = int(context_size)
        self._max_tokens = int(max_tokens)
        self._temperature = float(temperature)
        self._top_p = float(top_p)
        self._repeat_penalty = float(repeat_penalty)
        self._n_threads = max(1, int(n_threads))
        self._model: Optional[object] = None

    def _get_model(self):
        if self._model is None:
            if not self._model_path.exists():
                raise FileNotFoundError(f"Chat model not found: {self._model_path}")
            from llama_cpp import Llama

            self._model = Llama(
                model_path=str(self._model_path),
                n_ctx=self._context_size,
                n_threads=self._n_threads,
                n_threads_batch=self._n_threads,
                n_batch=min(512, self._context_size),
                verbose=False,
            )
        return self._model

    def answer(
        self,
        question: str,
        context_chunks: List[str],
        token_callback: TokenCallback = None,
        cancel_callback: CancelCallback = None,
    ) -> str:
        context_text = "\n\n---\n\n".join(context_chunks)
        messages = [
            {
                "role": "system",
                "content": (
                    "You answer questions from supplied document excerpts. "
                    "Answer directly and concisely. Do not output reasoning, "
                    "analysis, or <think> tags. If the excerpts are insufficient, "
                    "say that clearly."
                ),
            },
            {
                "role": "user",
                "content": (
                    "/no_think\n"
                    f"Question: {question}\n\n"
                    f"Document excerpts:\n{context_text}\n\n"
                    "Return only the final answer."
                ),
            },
        ]

        stream = self._create_chat_stream(messages)
        text_filter = _ThinkingTextFilter()
        visible_pieces: List[str] = []

        try:
            for event in stream:
                if cancel_callback is not None and cancel_callback():
                    raise InterruptedError("Answer generation cancelled.")

                raw_piece = self._extract_content(event)
                if not raw_piece:
                    continue

                visible_piece = text_filter.feed(raw_piece)
                if not visible_piece:
                    continue

                visible_pieces.append(visible_piece)
                if token_callback is not None:
                    token_callback(visible_piece)
        finally:
            close_method = getattr(stream, "close", None)
            if callable(close_method):
                close_method()

        remaining = text_filter.finish()
        if remaining:
            visible_pieces.append(remaining)
            if token_callback is not None:
                token_callback(remaining)

        answer = "".join(visible_pieces).strip()
        if not answer:
            raise RuntimeError("The local LLM returned an empty final answer.")
        return answer

    def _create_chat_stream(self, messages: List[dict]):
        model = self._get_model()
        common_arguments = {
            "messages": messages,
            "max_tokens": self._max_tokens,
            "temperature": self._temperature,
            "top_p": self._top_p,
            "repeat_penalty": self._repeat_penalty,
            "stream": True,
        }
        try:
            return model.create_chat_completion(
                **common_arguments,
                chat_template_kwargs={"enable_thinking": False},
            )
        except TypeError:
            return model.create_chat_completion(**common_arguments)

    def _extract_content(self, event: object) -> str:
        if not isinstance(event, dict):
            return ""
        choices = event.get("choices", [])
        if not choices:
            return ""
        choice = choices[0]
        if not isinstance(choice, dict):
            return ""
        delta = choice.get("delta", {})
        if isinstance(delta, dict):
            content = delta.get("content")
            if isinstance(content, str):
                return content
        text = choice.get("text")
        return text if isinstance(text, str) else ""
