import re
from balanced_latex_reader import BalancedLatexReader
from package_registry import PackageRegistry
from parsed_document import ParsedDocument


class PreambleCollector:
    def __init__(self, balanced_reader: BalancedLatexReader, package_registry: PackageRegistry) -> None:
        self.balanced_reader = balanced_reader
        self.package_registry = package_registry
        self.command_blocks = []
        self.command_block_keys = set()
        self.tikz_libraries = []
        self.graph_drawing_libraries = []
        self.warnings = []

    def collect(self, documents: list[ParsedDocument]) -> None:
        for document in documents:
            self.collect_from_preamble(document.preamble)
        self.ensure_requirements_for_documents(documents)

    def ensure_requirements_for_documents(self, documents: list[ParsedDocument]) -> None:
        combined_content = "\n".join(document.body for document in documents)
        if "\\includegraphics" in combined_content:
            self.package_registry.ensure_package("graphicx")
        if "\\includepdf" in combined_content:
            self.package_registry.ensure_package("pdfpages")
        if "\\includesvg" in combined_content:
            self.package_registry.ensure_package("svg")
        if "\\begin{minted}" in combined_content:
            self.package_registry.ensure_package("minted")
        if "\\url{" in combined_content or "\\href{" in combined_content:
            self.package_registry.ensure_package("hyperref")
        uses_tikz = "\\begin{tikzpicture}" in combined_content or bool(self.tikz_libraries) or bool(self.graph_drawing_libraries)
        if uses_tikz:
            self.package_registry.ensure_package("tikz")
            common_tikz_libraries = (
                "arrows.meta", "positioning", "calc", "shapes.geometric",
                "fit", "backgrounds", "patterns", "decorations.pathreplacing",
            )
            for library_name in common_tikz_libraries:
                if library_name not in self.tikz_libraries:
                    self.tikz_libraries.append(library_name)

    def collect_from_preamble(self, preamble: str) -> None:
        if not preamble.strip():
            return
        self.package_registry.collect(preamble)
        self.collect_library_command(preamble, "usetikzlibrary", self.tikz_libraries)
        self.collect_library_command(preamble, "usegdlibrary", self.graph_drawing_libraries)
        masked_preamble = self.balanced_reader.mask_comments(preamble)
        protected_ranges = []
        candidates = []
        candidates.extend(self.collect_delimited_blocks(preamble, masked_preamble, "makeatletter", "makeatother", protected_ranges))
        candidates.extend(self.collect_delimited_blocks(preamble, masked_preamble, "ExplSyntaxOn", "ExplSyntaxOff", protected_ranges))
        candidates.extend(self.collect_safe_command_blocks(preamble, masked_preamble, protected_ranges))
        candidates.sort(key=lambda item: item[0])
        for start_index, command_block in candidates:
            self.add_command_block(command_block)

    def collect_library_command(self, preamble: str, command_name: str, destination: list[str]) -> None:
        masked_preamble = self.balanced_reader.mask_comments(preamble)
        pattern = re.compile(r"\\" + re.escape(command_name) + r"\s*")
        for match in pattern.finditer(masked_preamble):
            index = self.balanced_reader.skip_whitespace(masked_preamble, match.end())
            if index >= len(masked_preamble) or masked_preamble[index] != "{":
                continue
            try:
                argument, end_index = self.balanced_reader.read_group(masked_preamble, index, "{", "}")
            except ValueError:
                continue
            if end_index <= index:
                continue
            for library_name in argument.split(","):
                normalized_library_name = library_name.strip()
                if normalized_library_name and normalized_library_name not in destination:
                    destination.append(normalized_library_name)

    def collect_delimited_blocks(self, preamble: str, masked_preamble: str, start_command: str, end_command: str, protected_ranges: list[tuple[int, int]]) -> list[tuple[int, str]]:
        candidates = []
        start_pattern = re.compile(r"\\" + re.escape(start_command) + r"\b")
        end_pattern = re.compile(r"\\" + re.escape(end_command) + r"\b")
        search_index = 0
        while True:
            start_match = start_pattern.search(masked_preamble, search_index)
            if start_match is None:
                break
            end_match = end_pattern.search(masked_preamble, start_match.end())
            if end_match is None:
                self.warnings.append(f"Skipped an unclosed preamble block: \\{start_command}")
                break
            block_end = end_match.end()
            protected_ranges.append((start_match.start(), block_end))
            candidates.append((start_match.start(), preamble[start_match.start():block_end].strip()))
            search_index = block_end
        return candidates

    def collect_safe_command_blocks(self, preamble: str, masked_preamble: str, protected_ranges: list[tuple[int, int]]) -> list[tuple[int, str]]:
        safe_commands = {
            "newcommand", "renewcommand", "providecommand", "newenvironment",
            "renewenvironment", "DeclareMathOperator", "DeclareMathOperator*",
            "DeclareRobustCommand", "NewDocumentCommand", "RenewDocumentCommand",
            "ProvideDocumentCommand", "DeclareDocumentCommand",
            "NewDocumentEnvironment", "RenewDocumentEnvironment",
            "ProvideDocumentEnvironment", "DeclarePairedDelimiter",
            "DeclarePairedDelimiterX", "newtheorem", "definecolor", "colorlet",
            "tikzset", "graphicspath", "hypersetup", "captionsetup", "lstset",
            "setminted", "usemintedstyle", "setcounter", "setlength",
            "addtolength", "setboolean", "AtBeginDocument", "AtEndDocument",
            "titleformat", "titlespacing", "geometry", "DeclareUnicodeCharacter",
            "setmainfont", "setsansfont", "setmonofont", "newfontfamily",
            "DeclareSIUnit", "numberwithin", "allowdisplaybreaks", "pagestyle",
            "fancyhf", "fancyhead", "fancyfoot", "renewpagestyle",
        }
        excluded_commands = {
            "documentclass", "usepackage", "RequirePackage", "PassOptionsToPackage",
            "input", "include", "subfile", "title", "author", "date",
            "bibliography", "bibliographystyle", "addbibresource",
            "printbibliography", "usetikzlibrary", "usegdlibrary",
            "makeatletter", "makeatother", "ExplSyntaxOn", "ExplSyntaxOff",
        }
        candidates = []
        index = 0
        while index < len(masked_preamble):
            if self.is_inside_ranges(index, protected_ranges):
                index = self.range_end_for_index(index, protected_ranges)
                continue
            if masked_preamble[index] != "\\":
                index += 1
                continue
            command_name, command_end = self.balanced_reader.read_command_name(masked_preamble, index)
            normalized_command_name = command_name
            star_index = self.balanced_reader.skip_whitespace(masked_preamble, command_end)
            if star_index < len(masked_preamble) and masked_preamble[star_index] == "*":
                normalized_command_name = command_name + "*"
            if normalized_command_name in excluded_commands or command_name in excluded_commands:
                index = self.skip_command(masked_preamble, command_end)
                continue
            if normalized_command_name not in safe_commands and command_name not in safe_commands:
                index = command_end
                continue
            block_end = self.find_command_block_end(masked_preamble, command_end)
            if block_end is None:
                self.warnings.append(f"Skipped an unbalanced preamble command: \\{command_name}")
                index = command_end
                continue
            command_block = preamble[index:block_end].strip()
            candidates.append((index, command_block))
            index = block_end
        return candidates

    def add_command_block(self, command_block: str) -> None:
        command_key = re.sub(r"\s+", "", command_block)
        if command_key and command_key not in self.command_block_keys:
            self.command_block_keys.add(command_key)
            self.command_blocks.append(command_block)

    def is_inside_ranges(self, index: int, protected_ranges: list[tuple[int, int]]) -> bool:
        for start_index, end_index in protected_ranges:
            if start_index <= index < end_index:
                return True
        return False

    def range_end_for_index(self, index: int, protected_ranges: list[tuple[int, int]]) -> int:
        for start_index, end_index in protected_ranges:
            if start_index <= index < end_index:
                return end_index
        return index + 1

    def skip_command(self, text: str, command_end: int) -> int:
        block_end = self.find_command_block_end(text, command_end)
        if block_end is None:
            return command_end
        return block_end

    def find_command_block_end(self, text: str, command_end: int) -> int | None:
        index = self.balanced_reader.skip_whitespace(text, command_end)
        if index < len(text) and text[index] == "*":
            index += 1
        found_group = False
        while index < len(text):
            index = self.balanced_reader.skip_whitespace(text, index)
            if index >= len(text):
                break
            if text[index] == "[":
                try:
                    argument, index = self.balanced_reader.read_group(text, index, "[", "]")
                except ValueError:
                    return None
                found_group = True
                continue
            if text[index] == "{":
                try:
                    argument, index = self.balanced_reader.read_group(text, index, "{", "}")
                except ValueError:
                    return None
                found_group = True
                continue
            break
        if found_group:
            while index < len(text) and text[index] in " \t":
                index += 1
            if index < len(text) and text[index] == "\n":
                index += 1
            return index
        line_end = text.find("\n", command_end)
        if line_end == -1:
            return len(text)
        return line_end + 1

    def render(self) -> str:
        sections = []
        package_text = self.package_registry.render()
        if package_text:
            sections.append(package_text)
        if self.tikz_libraries:
            sections.append("\\usetikzlibrary{" + ",".join(self.tikz_libraries) + "}")
        if self.graph_drawing_libraries:
            sections.append("\\usegdlibrary{" + ",".join(self.graph_drawing_libraries) + "}")
        if self.command_blocks:
            sections.append("\n\n".join(self.command_blocks))
        return "\n\n".join(sections)
