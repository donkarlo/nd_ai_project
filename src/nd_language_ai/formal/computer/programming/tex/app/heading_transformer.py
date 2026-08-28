import re
from balanced_latex_reader import BalancedLatexReader


class HeadingTransformer:
    def __init__(self, balanced_reader: BalancedLatexReader, starting_heading: str, document_class: str) -> None:
        self.balanced_reader = balanced_reader
        self.starting_heading = starting_heading
        self.document_class = document_class
        self.heading_commands = ["part", "chapter", "section", "subsection", "subsubsection", "paragraph", "subparagraph"]
        if document_class in {"article", "scrartcl"}:
            self.heading_commands.remove("chapter")
        self.starting_index = self.heading_commands.index(starting_heading)

    def transform(self, body: str, folder_depth: int) -> str:
        masked_body = self.balanced_reader.mask_comments(body)
        pattern = re.compile(r"\\(part|chapter|section|subsection|subsubsection|subsubsubsection|paragraph|subparagraph)(\*)?\s*")
        output_parts = []
        source_index = 0
        for match in pattern.finditer(masked_body):
            argument_index = self.balanced_reader.skip_whitespace(masked_body, match.end())
            optional_argument_text = ""
            if argument_index < len(masked_body) and masked_body[argument_index] == "[":
                try:
                    optional_argument, argument_index = self.balanced_reader.read_group(masked_body, argument_index, "[", "]")
                    optional_argument_text = "[" + optional_argument + "]"
                except ValueError:
                    continue
                argument_index = self.balanced_reader.skip_whitespace(masked_body, argument_index)
            if argument_index >= len(masked_body) or masked_body[argument_index] != "{":
                continue
            try:
                title, end_index = self.balanced_reader.read_group(masked_body, argument_index, "{", "}")
            except ValueError:
                continue
            output_parts.append(body[source_index:match.start()])
            original_command = match.group(1)
            if original_command == "subsubsubsection":
                original_index = self.heading_commands.index("paragraph")
            else:
                original_index = self.heading_commands.index(original_command)
            target_index = self.starting_index + folder_depth + original_index
            transformed_heading = self.render_heading(target_index, title, match.group(2) == "*", optional_argument_text)
            output_parts.append(transformed_heading)
            source_index = end_index
        output_parts.append(body[source_index:])
        return "".join(output_parts)

    def render_heading(self, target_index: int, title: str, starred: bool, optional_argument_text: str) -> str:
        if target_index < len(self.heading_commands):
            if starred:
                star_text = "*"
            else:
                star_text = ""
            return f"\\{self.heading_commands[target_index]}{star_text}{optional_argument_text}{{{title}}}"
        deep_level = target_index - len(self.heading_commands) + 1
        return f"\\ProjectDeepHeading{{{deep_level}}}{{{title}}}"

    def render_folder_heading(self, folder_depth: int, folder_name: str) -> str:
        target_index = self.starting_index + folder_depth - 1
        readable_name = self.humanize_name(folder_name)
        return self.render_heading(target_index, readable_name, False, "")

    def humanize_name(self, name: str) -> str:
        readable_name = name.replace("_", " ").replace("-", " ").strip()
        if not readable_name:
            return "Untitled"
        return readable_name[:1].upper() + readable_name[1:]
