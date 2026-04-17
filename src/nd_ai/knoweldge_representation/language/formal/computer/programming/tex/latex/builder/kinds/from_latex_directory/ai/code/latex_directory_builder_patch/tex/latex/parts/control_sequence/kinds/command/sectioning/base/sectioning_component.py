try:
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.composition.composite import Composite
except ImportError:
    from ......composition.composite import Composite


class SectioningComponent(Composite):
    def __init__(self, command_name: str, title: str = None):
        Composite.__init__(self)
        self._command_name = command_name
        self._title = title

    def get_title(self) -> str:
        return self._title

    def set_title(self, title: str) -> None:
        self._title = title
        self.invalidate_cached_string()

    def stringify(self) -> str:
        pieces = []
        if self._title is not None:
            pieces.append("\\" + self._command_name + "{" + self._title + "}\n")
        for child in self.get_child_group_members():
            pieces.append(child.stringify())
        return ''.join(pieces)
