from abc import ABC, abstractmethod

try:
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.builder.kinds.core.kinds import Kinds
except ImportError:
    from .kinds.core.kinds import Kinds


class Builder(ABC):
    def __init__(self, kind: str):
        self._kind = kind
        self._string_composition = None

    def get_tex_composite(self):
        return getattr(self, "_composite_structure", None)

    def _build_composition(self) -> None:
        pass

    @abstractmethod
    def get_string_from_composition(self) -> str:
        raise NotImplementedError
