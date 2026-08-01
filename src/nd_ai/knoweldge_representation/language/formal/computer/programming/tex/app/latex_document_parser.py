import re
from pathlib import Path
from balanced_latex_reader import BalancedLatexReader
from parsed_document import ParsedDocument
from source_file import SourceFile


class LatexDocumentParser:
    def __init__(self, balanced_reader: BalancedLatexReader) -> None:
        self.balanced_reader = balanced_reader

    def parse(self, source_file: SourceFile) -> ParsedDocument:
        content = source_file.content
        preamble, body, is_full_document = self.split_documents(content)
        if not is_full_document:
            masked_content = self.balanced_reader.mask_comments(content)
            if self.looks_like_preamble_fragment(source_file.path, masked_content):
                preamble = content
                body = ""
            else:
                preamble = ""
                body = content
        title = self.extract_first_argument(preamble, "title")
        preamble_dependencies = tuple(self.extract_command_arguments(preamble, ("input", "include", "subfile")))
        body_dependencies = tuple(self.extract_command_arguments(body, ("input", "include", "subfile")))
        bibliography_references = self.extract_bibliography_references(content)
        bibliography_style = self.extract_first_argument(content, "bibliographystyle")
        is_preamble_fragment = body == "" and preamble != ""
        return ParsedDocument(source_file, preamble, body, title, preamble_dependencies, body_dependencies, bibliography_references, bibliography_style, is_full_document, is_preamble_fragment)

    def split_documents(self, content: str) -> tuple[str, str, bool]:
        masked_content = self.balanced_reader.mask_comments(content)
        begin_matches = list(re.finditer(r"\\begin\s*\{document\}", masked_content))
        end_matches = list(re.finditer(r"\\end\s*\{document\}", masked_content))
        if not begin_matches or not end_matches:
            return "", content, False
        preamble_parts = []
        body_parts = []
        search_start = 0
        end_match_index = 0
        paired_document_count = 0
        for begin_match in begin_matches:
            while end_match_index < len(end_matches) and end_matches[end_match_index].start() < begin_match.end():
                end_match_index += 1
            if end_match_index >= len(end_matches):
                break
            end_match = end_matches[end_match_index]
            preamble_parts.append(content[search_start:begin_match.start()])
            body_parts.append(content[begin_match.end():end_match.start()])
            search_start = end_match.end()
            end_match_index += 1
            paired_document_count += 1
        if paired_document_count == 0:
            return "", content, False
        trailing_content = content[search_start:]
        if trailing_content.strip():
            if self.looks_like_preamble_fragment(Path("trailing.tex"), self.balanced_reader.mask_comments(trailing_content)):
                preamble_parts.append(trailing_content)
            else:
                body_parts.append(trailing_content)
        return "\n\n".join(preamble_parts), "\n\n".join(body_parts), True

    def looks_like_preamble_fragment(self, path: Path, masked_content: str) -> bool:
        lower_parts = {part.casefold() for part in path.parts}
        if "preamble" in lower_parts or "conf" in lower_parts or "config" in lower_parts:
            return True
        commands = re.findall(r"\\([A-Za-z@]+)", masked_content)
        if not commands:
            return False
        body_commands = {
            "part", "chapter", "section", "subsection", "subsubsection",
            "paragraph", "subparagraph", "item", "caption", "includegraphics",
            "includepdf", "includesvg", "cite", "citet", "citep", "footnote",
            "tableofcontents", "maketitle",
        }
        if any(command in body_commands for command in commands):
            return False
        body_environment_pattern = re.compile(
            r"\\begin\s*\{(?:document|figure|table|equation|align|gather|itemize|enumerate|description|minted|verbatim|lstlisting)\}",
            flags=re.IGNORECASE,
        )
        if body_environment_pattern.search(masked_content) is not None:
            return False
        preamble_commands = {
            "documentclass", "usepackage", "RequirePackage", "PassOptionsToPackage",
            "newcommand", "renewcommand", "providecommand", "newenvironment",
            "renewenvironment", "DeclareMathOperator", "DeclareRobustCommand",
            "NewDocumentCommand", "RenewDocumentCommand", "ProvideDocumentCommand",
            "NewDocumentEnvironment", "RenewDocumentEnvironment",
            "definecolor", "tikzset", "usetikzlibrary", "usegdlibrary",
            "graphicspath", "hypersetup", "captionsetup", "setminted",
            "usemintedstyle", "setcounter", "setlength", "AtBeginDocument",
            "AtEndDocument", "titleformat", "titlespacing", "geometry",
            "DeclareUnicodeCharacter", "makeatletter", "makeatother",
            "ExplSyntaxOn", "ExplSyntaxOff", "@ifpackageloaded",
        }
        matching_count = sum(1 for command in commands if command in preamble_commands)
        if matching_count >= 2:
            return True
        package_anchor_commands = {"documentclass", "usepackage", "RequirePackage"}
        if any(command in package_anchor_commands for command in commands):
            text_without_commands = re.sub(r"\\[A-Za-z@]+", "", masked_content)
            text_without_groups = re.sub(r"[{}\[\],=*0-9._:/#&()'\"+-]", "", text_without_commands)
            meaningful_text = "".join(character for character in text_without_groups if character.isalpha())
            return len(meaningful_text) < 250
        return False

    def extract_command_arguments(self, text: str, command_names: tuple[str, ...]) -> list[str]:
        arguments = []
        masked_text = self.balanced_reader.mask_comments(text)
        command_pattern = "|".join(re.escape(command_name) for command_name in command_names)
        pattern = re.compile(r"\\(?:" + command_pattern + r")\s*")
        for match in pattern.finditer(masked_text):
            index = self.balanced_reader.skip_whitespace(masked_text, match.end())
            if index < len(masked_text) and masked_text[index] == "{":
                try:
                    argument, end_index = self.balanced_reader.read_group(masked_text, index, "{", "}")
                    if end_index > index:
                        arguments.append(argument.strip())
                except ValueError:
                    continue
        return arguments

    def extract_first_argument(self, text: str, command_name: str) -> str:
        arguments = self.extract_command_arguments(text, (command_name,))
        if arguments:
            return arguments[0]
        return ""

    def extract_bibliography_references(self, text: str) -> tuple[str, ...]:
        references = []
        for argument in self.extract_command_arguments(text, ("bibliography", "addbibresource")):
            for reference in argument.split(","):
                normalized_reference = reference.strip()
                if normalized_reference:
                    references.append(normalized_reference)
        return tuple(references)
