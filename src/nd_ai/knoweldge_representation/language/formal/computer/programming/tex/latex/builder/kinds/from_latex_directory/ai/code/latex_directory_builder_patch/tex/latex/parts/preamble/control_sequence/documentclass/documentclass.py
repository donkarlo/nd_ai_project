from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.composition.leaf import Leaf


class Documentclass(Leaf):
    def __init__(self, class_name: str = 'book', optional_argument: str = None):
        Leaf.__init__(self)
        self._class_name = class_name
        self._optional_argument = optional_argument

    def stringify(self) -> str:
        optional = ''
        if self._optional_argument is not None and len(str(self._optional_argument)) > 0:
            optional = '[' + str(self._optional_argument) + ']'
        return "\\documentclass" + optional + "{" + self._class_name + "}\n"
