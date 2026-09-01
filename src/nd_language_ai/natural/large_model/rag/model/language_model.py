from abc import ABC, abstractmethod
from typing import Callable, List, Optional


TokenCallback = Optional[Callable[[str], None]]
CancelCallback = Optional[Callable[[], bool]]


class LanguageModel(ABC):
    @abstractmethod
    def answer(
        self,
        question: str,
        context_chunks: List[str],
        token_callback: TokenCallback = None,
        cancel_callback: CancelCallback = None,
    ) -> str:
        raise NotImplementedError
