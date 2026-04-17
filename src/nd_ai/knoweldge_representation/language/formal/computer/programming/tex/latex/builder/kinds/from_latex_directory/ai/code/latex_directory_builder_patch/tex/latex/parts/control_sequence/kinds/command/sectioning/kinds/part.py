try:
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.control_sequence.kinds.command.sectioning.base.sectioning_component import SectioningComponent
except ImportError:
    from ..base.sectioning_component import SectioningComponent


class Part(SectioningComponent):
    def __init__(self, title: str = None):
        SectioningComponent.__init__(self, 'part', title)
