try:
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.composition.component import Component as LatexComponent
except ImportError:
    from .component import Component as LatexComponent

from nd_utility.oop.design_pattern.structural.composition.composite import Composite as BaseComposite


class Composite(LatexComponent, BaseComposite):
    def __init__(self):
        LatexComponent.__init__(self)
        BaseComposite.__init__(self)

    def add_child(self, child):
        BaseComposite.add_child(self, child)
        self.invalidate_cached_string()

    def remove_child(self, child):
        BaseComposite.remove_child(self, child)
        self.invalidate_cached_string()
