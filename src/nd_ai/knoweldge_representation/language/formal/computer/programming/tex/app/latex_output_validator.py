import re
from balanced_latex_reader import BalancedLatexReader


class LatexOutputValidator:
    def __init__(self, balanced_reader: BalancedLatexReader, bibliography_path: str) -> None:
        self.balanced_reader = balanced_reader
        self.bibliography_path = bibliography_path

    def validate(self, content: str) -> None:
        self.validate_document_commands(content)
        self.validate_bibliography(content)
        self.validate_known_corruptions(content)
        self.validate_preamble_braces(content)

    def validate_document_commands(self, content: str) -> None:
        expected_counts = {
            "\\documentclass": 1,
            "\\begin{document}": 1,
            "\\end{document}": 1,
        }
        for command, expected_count in expected_counts.items():
            actual_count = content.count(command)
            if actual_count != expected_count:
                raise ValueError(f"Generated LaTeX contains {actual_count} occurrences of {command}; expected {expected_count}.")

    def validate_bibliography(self, content: str) -> None:
        bibliography_style = "\\bibliographystyle{plainnat}"
        bibliography_command = f"    \\bibliography{{{self.bibliography_path}}}"
        if content.count(bibliography_style) != 1:
            raise ValueError("Generated LaTeX must contain exactly one plainnat bibliography style command.")
        if content.count(bibliography_command) != 1:
            raise ValueError("Generated LaTeX must contain exactly one configured bibliography command.")
        required_ending = bibliography_style + "\n" + bibliography_command + "\n\n\\end{document}\n"
        if not content.endswith(required_ending):
            raise ValueError("The bibliography commands are not immediately before the final document ending.")

    def validate_known_corruptions(self, content: str) -> None:
        corrupt_patterns = (
            r"\\\{\}\{",
            r"\\makeatletter\s*\\\{",
        )
        for pattern in corrupt_patterns:
            if re.search(pattern, content) is not None:
                raise ValueError(f"Generated LaTeX contains a known malformed construct: {pattern}")

    def validate_preamble_braces(self, content: str) -> None:
        begin_document_index = content.find("\\begin{document}")
        preamble = content[:begin_document_index]
        masked_preamble = self.balanced_reader.mask_comments(preamble)
        brace_depth = 0
        for index, character in enumerate(masked_preamble):
            if self.balanced_reader.is_escaped(masked_preamble, index):
                continue
            if character == "{":
                brace_depth += 1
            elif character == "}":
                brace_depth -= 1
                if brace_depth < 0:
                    raise ValueError("Generated LaTeX preamble contains an extra closing brace.")
        if brace_depth != 0:
            raise ValueError("Generated LaTeX preamble contains unbalanced braces.")
