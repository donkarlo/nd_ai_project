from nd_ai.language.formal.computer.programming.latex.component import Component
from nd_utility.oop.design_pattern.structural.composition.leaf import Leaf as BaseLeaf

class Leaf(Component, BaseLeaf):
    def __init__(self):
        BaseLeaf.__init__(self)