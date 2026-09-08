from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.part.environment.environment import Environment
from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.part.environment.kind.list.kind.itemize import \
    Itemize


class Document(Environment):
    def __init__(self):
        self._allowed_children_kinds = [Itemize]


