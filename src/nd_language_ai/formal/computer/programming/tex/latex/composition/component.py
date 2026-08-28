from abc import abstractmethod

from nd_utility.oop.design_pattern.structural.composition.component import Component as BaseComponent
from typing import Optional

class Component(BaseComponent):
    def __init__(self):
        BaseComponent.__init__(self)

        self._composed_string = None

    def get_composed_string(self) -> str:
        if self._composed_string is None:
            self._composed_string = self.stringify()

    @abstractmethod
    def stringify(self) -> str:
        ...