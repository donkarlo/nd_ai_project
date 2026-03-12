
from nd_ai.language.formal.computer.programming.latex.component import Component
from nd_utility.oop.design_pattern.structural.composition.composite import Composite as BaseComposite


class Latex(Component, BaseComposite):
    def __init__(self):
        BaseComposite.__init__(self)
        Component.__init__(self)
