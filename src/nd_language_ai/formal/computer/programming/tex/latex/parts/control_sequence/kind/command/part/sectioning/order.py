from typing import List

from parts.control_sequence.kind.command.part.sectioning.kinds.chapter import \
    Chapter
from parts.control_sequence.kind.command.part.sectioning.kinds.paragraph import \
    Paragraph
from parts.control_sequence.kind.command.part.sectioning.kinds.part import \
    Part
from parts.control_sequence.kind.command.part.sectioning.kinds.section import \
    Section
from parts.control_sequence.kind.command.part.sectioning.kinds.subparagraph import \
    Subparagraph
from parts.control_sequence.kind.command.part.sectioning.kinds.subsection import \
    Subsection
from parts.control_sequence.kind.command.part.sectioning.kinds.subsubsection import \
    Subsubsection


class Order:
    def __init__(self):
        self._ordered_sections = [Part, Chapter, Section, Subsection, Subsubsection, Paragraph, Subparagraph]

    def get_ordered_sections(self) -> List:
        return self._ordered_sections
