try:
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.composition.leaf import Leaf
except ImportError:
    from .....composition.leaf import Leaf


class Bibliography(Leaf):
    def __init__(self, bibliography_path: str):
        Leaf.__init__(self)
        self._bibliography_path = bibliography_path

    def stringify(self) -> str:
        return "\\bibliography{" + self._bibliography_path + "}\n"
