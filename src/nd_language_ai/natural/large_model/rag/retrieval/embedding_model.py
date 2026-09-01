from abc import ABC, abstractmethod
from typing import Callable, List, Optional

import numpy as np


ProgressCallback = Optional[Callable[[str], None]]


class EmbeddingModel(ABC):
    @abstractmethod
    def embed_one(self, text: str) -> np.ndarray:
        raise NotImplementedError

    @abstractmethod
    def embed_many(
        self,
        texts: List[str],
        progress_callback: ProgressCallback = None,
    ) -> np.ndarray:
        raise NotImplementedError
