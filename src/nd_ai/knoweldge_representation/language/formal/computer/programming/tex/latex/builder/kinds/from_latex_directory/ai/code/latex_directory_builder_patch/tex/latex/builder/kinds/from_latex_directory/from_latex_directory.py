import os
from pathlib import Path

try:
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.builder.builder import Builder
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.builder.kinds.core.kinds import Kinds
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.latex import Latex
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.environment.kind.document.document import Document
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.preamble.preamble import Preamble
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.preamble.control_sequence.documentclass.documentclass import Documentclass
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.raw.raw_latex import RawLatex
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.parts.control_sequence.kinds.command.bibliography.bibliography import Bibliography
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.builder.kinds.from_latex_directory.parser.latex_file_parser import LatexFileParser
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.builder.kinds.from_latex_directory.preamble.preamble_command_collector import PreambleCommandCollector
    from nd_ai.knoweldge_representation.language.formal.computer.programming.tex.latex.builder.kinds.from_latex_directory.node.sectioning_node_factory import SectioningNodeFactory
except ImportError:
    from ...builder import Builder
    from ..core.kinds import Kinds
    from ....latex import Latex
    from ....parts.environment.kind.document.document import Document
    from ....parts.preamble.preamble import Preamble
    from ....parts.preamble.control_sequence.documentclass.documentclass import Documentclass
    from ....parts.raw.raw_latex import RawLatex
    from ....parts.control_sequence.kinds.command.bibliography.bibliography import Bibliography
    from .parser.latex_file_parser import LatexFileParser
    from .preamble.preamble_command_collector import PreambleCommandCollector
    from .node.sectioning_node_factory import SectioningNodeFactory


class FromLatexDirectory(Builder):
    def __init__(self, root_directory, bibliography_file, start_part: str):
        Builder.__init__(self, Kinds.FROM_LATEX_DIRECTORY)
        self._starting_part = start_part
        self._latex_start_directory = Path(os.fspath(root_directory))
        self._shared_bibliography = Path(os.fspath(bibliography_file))
        self._composite_structure = None
        self._preamble = None
        self._document_environment = None
        self._bibliography = None
        self._parser = LatexFileParser()
        self._preamble_collector = PreambleCommandCollector()
        self._sectioning_node_factory = SectioningNodeFactory()
        self._visited_files = set()

    def build_latex(self) -> Latex:
        self._composite_structure = Latex()
        self._preamble = Preamble()
        self._document_environment = Document()
        self._bibliography = Bibliography(self._get_bibliography_argument())

        self._composite_structure.add_child(Documentclass())
        self._composite_structure.add_child(self._preamble)
        self._composite_structure.add_child(self._document_environment)

        root_node = self._sectioning_node_factory.create(self._starting_part, self._latex_start_directory.name)
        self._document_environment.add_child(root_node)

        self._build_from_directory(self._latex_start_directory, root_node)

        for preamble_line in self._preamble_collector.get_lines():
            self._preamble.add_child(RawLatex(preamble_line + '\n'))

        self._document_environment.add_child(self._bibliography)
        return self._composite_structure

    def _build_from_directory(self, current_directory_path: Path, parent_node) -> None:
        if not current_directory_path.exists() or not current_directory_path.is_dir():
            return

        anchor_file_path = self._find_anchor_tex_file(current_directory_path)
        explicitly_ordered_paths = []

        if anchor_file_path is not None:
            explicitly_ordered_paths = self._consume_file_into_node(anchor_file_path, parent_node)

        direct_tex_files = self._get_direct_tex_files(current_directory_path)
        remaining_tex_files = []
        for tex_file_path in direct_tex_files:
            resolved_path = tex_file_path.resolve()
            if resolved_path in self._visited_files:
                continue
            remaining_tex_files.append(tex_file_path)

        for tex_file_path in sorted(remaining_tex_files, key=lambda path: path.name.lower()):
            self._consume_file_into_node(tex_file_path, parent_node)

        for child_directory_path in sorted([path for path in current_directory_path.iterdir() if path.is_dir()], key=lambda path: path.name.lower()):
            child_anchor = self._find_anchor_tex_file(child_directory_path)
            if child_anchor is not None and child_anchor.resolve() in self._visited_files:
                continue
            child_node = self._sectioning_node_factory.create(self._starting_part, child_directory_path.name)
            parent_node.add_child(child_node)
            self._build_from_directory(child_directory_path, child_node)

    def _consume_file_into_node(self, file_path: Path, parent_node):
        resolved = file_path.resolve()
        if resolved in self._visited_files:
            return []
        self._visited_files.add(resolved)

        parsed_file = self._parser.parse_file(str(file_path))

        if parsed_file.is_complete_document():
            self._preamble_collector.add_lines(parsed_file.get_preamble_lines())

        body_string = parsed_file.get_body_string()
        if len(body_string.strip()) > 0:
            parent_node.add_child(RawLatex(body_string if body_string.endswith('\n') else body_string + '\n'))

        ordered_includes = []
        for included_relative_path in parsed_file.get_included_relative_paths():
            resolved_include_file = self._resolve_include_path(file_path.parent, included_relative_path)
            if resolved_include_file is None:
                continue
            ordered_includes.append(resolved_include_file)
            self._consume_file_into_node(resolved_include_file, parent_node)

        return ordered_includes

    def _resolve_include_path(self, base_directory_path: Path, included_relative_path: str):
        candidate = base_directory_path / included_relative_path
        if candidate.suffix.lower() != '.tex':
            tex_candidate = Path(str(candidate) + '.tex')
            if tex_candidate.exists():
                return tex_candidate
        if candidate.exists():
            return candidate
        return None

    def _find_anchor_tex_file(self, directory_path: Path):
        candidate = directory_path / (directory_path.name + '.tex')
        if candidate.exists():
            return candidate
        return None

    def _get_direct_tex_files(self, directory_path: Path):
        return [path for path in directory_path.iterdir() if path.is_file() and path.suffix.lower() == '.tex']

    def _get_bibliography_argument(self) -> str:
        bibliography_string = str(self._shared_bibliography)
        if bibliography_string.lower().endswith('.bib'):
            bibliography_string = bibliography_string[:-4]
        return bibliography_string

    def build_composed_string(self) -> str:
        if self._composite_structure is None:
            self.build_latex()
        self._string_composition = self._composite_structure.stringify()
        return self._string_composition

    def get_string_from_composition(self) -> str:
        return self.build_composed_string()

    def save_composed_string_to_tex_file(self, file) -> bool:
        output_path = Path(os.fspath(file))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(self.build_composed_string(), encoding='utf-8')
        return True
