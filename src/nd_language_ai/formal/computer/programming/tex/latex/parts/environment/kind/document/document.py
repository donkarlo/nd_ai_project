from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.environment.environment import Environment
from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.environment.kind.list.kinds.itemize import \
    Itemize


class Document(Environment):
    def __init__(self):
        self._allowed_children_kinds = [Itemize]


