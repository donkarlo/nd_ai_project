from nd_ai.language.formal.computer.programming.latex.builder.builder import Builder
from nd_ai.language.formal.computer.programming.tex.composition.composite import Composite as TexComposite
from nd_utility.os.file_system.path.directory import Directory


class FromTexDirectory(Builder):
    def __init__(self, project_directory: Directory, bibliography_directory: Directory):
        """
        instructions:
            strat from the given directory and search for the .builder file naming exactly the same as the given directory name.

        Args:
            project_directory:

        GPT generation instruction:
        - find the file that has
        """
        self._root_tex_composite = TexComposite()
        self._preamble = TexComposite()
        self._document = TexComposite()
        self._bibliography = TexComposite()

        #
        self._root_tex_composite.add_child(self._preamble)
        self._document.add_child(self._bibliography)





        # Lazy loading
        self._composed_string = None

    def get_composed_string(self)->str:
        if self._composed_string is None:
            for child in self._root_tex_composite.walk():
                self._composed_string += child.stringify()

if __name__ == "__main__":
    directory_path = "/home/donkarlo/Dropbox/repo/research_publication/src/kind/journal_2026/"


    composing_from_text_directory = FromTexDirectory(directory_path)
    composing_from_text_directory.get_composed_string(Directory(file_path))