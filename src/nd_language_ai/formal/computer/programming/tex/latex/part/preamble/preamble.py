from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.composition.composite import \
    Composite
from parts.environment.kind.document.document import Document
from parts.preamble.part.author.author import Author
from parts.preamble.part.date.date import Date
from parts.preamble.part.title.title import Title


class Preamble(Composite):
    def __init__(self):
        self.add_child(Title())
        self.add_child(Document())
        self.add_child(Date())
        self.add_child(Author())
