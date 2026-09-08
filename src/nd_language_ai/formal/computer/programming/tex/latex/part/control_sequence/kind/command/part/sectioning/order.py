from typing import List

from parts.control_sequence.kind.command.part.sectioning.kind.chapter import \
    Chapter
from parts.control_sequence.kind.command.part.sectioning.kind.paragraph import \
    Paragraph
from parts.control_sequence.kind.command.part.sectioning.kind.part import \
    Part
from parts.control_sequence.kind.command.part.sectioning.kind.section import \
    Section
from parts.control_sequence.kind.command.part.sectioning.kind.subparagraph import \
    Subparagraph
from parts.control_sequence.kind.command.part.sectioning.kind.subsection import \
    Subsection
from parts.control_sequence.kind.command.part.sectioning.kind.subsubsection import \
    Subsubsection


class Order:
    def __init__(self):
        self._ordered_sections = [Part, Chapter, Section, Subsection, Subsubsection, Paragraph, Subparagraph]

    def get_ordered_sections(self) -> List:
        return self._ordered_sections
