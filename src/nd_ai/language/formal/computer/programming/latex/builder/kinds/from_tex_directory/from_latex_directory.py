from nd_ai.language.formal.computer.programming.latex.builder.builder import Builder
from nd_ai.language.formal.computer.programming.latex.latex import Latex as LatexCompositeComponent
from nd_utility.os.file_system.path.directory import Directory


class FromLatexDirectory(Builder):
    def __init__(self, project_directory: Directory, bibliography_directory: Directory):
        """
        instructions:
            strat from the given directory and search for the .builder file naming exactly the same as the given directory name.

        Args:
            project_directory:

        GPT generation instruction:
        You must generate a single .tex file with all necessary packages etc in that you have seen recursively in the directories wthat are direct children of the given directory. No use packages or commands should not be repeated. Thatswhy you build a document in a composite (pattern) document.
        - find the file that has the same name as the given directory name.
        - look at the relative paths that are included or inputed by the order they appear in that file. When finshed the in recursively by alphabets go inside the files and first follow the inputs and the includes and add them to the document tree. also add the packages that already dont exist inside the current preamble
        """
        self._root_latex_composite = LatexCompositeComponent()
        self._preamble = LatexCompositeComponent()
        self._document = LatexCompositeComponent()
        self._bibliography = LatexCompositeComponent()

        #
        self._root_latex_composite.add_child(self._preamble)
        self._root_latex_composite.add_child(self._document)
        self._document.add_child(self._bibliography)





        # Lazy loading
        self._composed_string = None

    def get_composed_string(self)->str:
        if self._composed_string is None:
            for child in self._root_latex_composite.walk():
                self._composed_string += child.stringify()

if __name__ == "__main__":
    directory_path = "/home/donkarlo/Dropbox/repo/research_publication/src/kind/journal_2026/"


    composing_from_text_directory = FromLatexDirectory(directory_path)
    composing_from_text_directory.get_composed_string(Directory(directory_path))