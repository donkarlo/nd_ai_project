from abc import ABC, abstractmethod
from pathlib import Path


class DocumentReader(ABC):
    @abstractmethod
    def read(self, file_path: Path) -> str:
        raise NotImplementedError
