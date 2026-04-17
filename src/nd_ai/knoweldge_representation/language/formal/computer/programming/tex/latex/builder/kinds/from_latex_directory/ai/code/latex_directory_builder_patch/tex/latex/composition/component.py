from abc import abstractmethod

from nd_utility.oop.design_pattern.structural.composition.component import Component as BaseComponent


class Component(BaseComponent):
    def __init__(self):
        BaseComponent.__init__(self)
        self._composed_string = None

    def get_composed_string(self) -> str:
        if self._composed_string is None:
            self._composed_string = self.stringify()
        return self._composed_string

    def invalidate_cached_string(self) -> None:
        self._composed_string = None
        parent = self.get_parent()
        while parent is not None:
            if hasattr(parent, 'invalidate_cached_string'):
                parent.invalidate_cached_string()
            parent = parent.get_parent()

    @abstractmethod
    def stringify(self) -> str:
        raise NotImplementedError
