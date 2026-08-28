from abc import abstractmethod

from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.builder.kind.core.kinds import Kinds


class Builder(ABC):
    def __init__(self, kind:Kinds):
        self._kind = kind
        self._string_composition = None

    def get_tex_composite(self):
        if self._kind == "from_latex_directory":
            pass

    def _build_composition(self)->None:
        pass

    @abstractmethod
    def get_string_from_composition(self)->str:
        pass