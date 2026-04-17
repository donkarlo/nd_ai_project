from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.composition.composite import Composite


class Environment(Composite):
    def __init__(self, name: str):
        Composite.__init__(self)
        self._name = name

    def get_environment_name(self) -> str:
        return self._name

    def stringify(self) -> str:
        body = ''.join(child.stringify() for child in self.get_child_group_members())
        return "\\begin{" + self._name + "}\n" + body + "\\end{" + self._name + "}\n"
