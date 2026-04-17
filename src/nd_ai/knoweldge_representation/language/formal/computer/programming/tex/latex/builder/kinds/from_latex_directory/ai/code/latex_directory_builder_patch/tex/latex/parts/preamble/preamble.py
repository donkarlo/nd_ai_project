try:
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.composition.composite import Composite
except ImportError:
    from ...composition.composite import Composite


class Preamble(Composite):
    def __init__(self):
        Composite.__init__(self)

    def stringify(self) -> str:
        return ''.join(child.stringify() for child in self.get_child_group_members())
