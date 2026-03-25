from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.builder.builder import Builder
from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.latex import \
    Latex as LatexCompositeComponent
from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.environment.kinds.document.document import \
    Document
from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.preamble.control_sequence.documentclass.documentclass import \
    Documentclass
from nd_utility.os.file_system.path.directory import Directory


class FromLatexDirectory(Builder):
    def __init__(self, root_directory: Directory, bibliography_directory: Directory):
        """

        """
        self._latex_start_directory = root_directory
        self._shared_bibliography = bibliography_directory

        self._root_latex_composite = LatexCompositeComponent()
        self._preamble = LatexCompositeComponent()
        self._document = Document()
        self._bibliography = LatexCompositeComponent()

        #
        self._root_latex_composite.add_child(self._preamble)
        self._preamble.add_child(Documentclass())
        self._root_latex_composite.add_child(self._document)
        self._document.add_child(self._bibliography)

        # Lazy loading
        self._composed_string = None

    def get_composed_string(self) -> str:
        if self._composed_string is None:
            for child in self._root_latex_composite.walk():
                self._composed_string += child.stringify()


if __name__ == "__main__":
    directory_path = "/home/donkarlo/Dropbox/repo/research_publication/src/kind/journal_2026/"

    bibliography_path = "/home/donkarlo/Dropbox/repo/nd_shared_research/bibliography/bibliography.bib"

    composing_from_text_directory = FromLatexDirectory(directory_path, bibliography_path)
    composing_from_text_directory.get_composed_string()
