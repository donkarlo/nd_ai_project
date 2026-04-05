from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.builder.builder import Builder
from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.latex import \
    Latex
from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.environment.kinds.document.document import \
    Document
from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.preamble.control_sequence.documentclass.documentclass import \
    Documentclass
from nd_utility.os.file_system.path.directory import Directory
from nd_utility.os.file_system.path.file import File


class FromLatexDirectory(Builder):
    def __init__(self, root_directory: Directory, bibliography_file: File):
        """

        """
        self._latex_start_directory = root_directory
        self._shared_bibliography = bibliography_file

    def build_latex(self) -> Latex:
        self._composite_structure = Latex()
        self._preamble = Latex()
        self._document = Document()
        self._bibliography = Latex()

        #
        self._composite_structure.add_child(self._preamble)
        self._preamble.add_child(Documentclass())
        self._composite_structure.add_child(self._document)
        self._document.add_child(self._bibliography)

        # Lazy loading
        self._composed_string = None

    def build_composed_string(self) -> str:
        if self._composite_structure is None:
            self.build_latex()

        if self._composed_string is None:
            for child in self._composite_structure.walk():
                self._composed_string += child.stringify()


    def save_composed_string_to_tex_file(self, file: File) -> bool:
        pass


if __name__ == "__main__":
    directory_path = "/home/donkarlo/Dropbox/repo/research_publication/src/kind/journal_2026/"

    bibliography_path = "/home/donkarlo/Dropbox/repo/nd_shared_research/bibliography/bibliography.bib"

    composing_from_text_directory = FromLatexDirectory(directory_path, bibliography_path)
    composing_from_text_directory.build_composed_string()
