from typing import List

try:
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.control_sequence.kinds.command.sectioning.kinds.chapter import Chapter
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.control_sequence.kinds.command.sectioning.kinds.paragraph import Paragraph
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.control_sequence.kinds.command.sectioning.kinds.part import Part
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.control_sequence.kinds.command.sectioning.kinds.section import Section
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.control_sequence.kinds.command.sectioning.kinds.subparagraph import Subparagraph
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.control_sequence.kinds.command.sectioning.kinds.subsection import Subsection
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.control_sequence.kinds.command.sectioning.kinds.subsubsection import Subsubsection
except ImportError:
    from .kinds.chapter import Chapter
    from .kinds.paragraph import Paragraph
    from .kinds.part import Part
    from .kinds.section import Section
    from .kinds.subparagraph import Subparagraph
    from .kinds.subsection import Subsection
    from .kinds.subsubsection import Subsubsection


class Order:
    def __init__(self):
        self._ordered_sections = [Part, Chapter, Section, Subsection, Subsubsection, Paragraph, Subparagraph]

    def get_ordered_sections(self) -> List:
        return self._ordered_sections
