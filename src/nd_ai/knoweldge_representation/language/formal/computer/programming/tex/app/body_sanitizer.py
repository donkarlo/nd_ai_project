import re
from balanced_latex_reader import BalancedLatexReader


class BodySanitizer:
    def __init__(self, balanced_reader: BalancedLatexReader) -> None:
        self.balanced_reader = balanced_reader
        self.seen_table_of_contents = False
        self.seen_list_of_todos = False

    def sanitize(self, body: str) -> str:
        sanitized_body = body
        sanitized_body = self.remove_document_commands(sanitized_body)
        sanitized_body = self.remove_dependency_commands(sanitized_body)
        sanitized_body = self.remove_bibliography_commands(sanitized_body)
        sanitized_body = self.remove_raw_bibliography_entries(sanitized_body)
        sanitized_body = self.remove_repeated_global_commands(sanitized_body)
        sanitized_body = self.wrap_python_like_blocks(sanitized_body)
        sanitized_body = self.normalize_quoted_text(sanitized_body)
        sanitized_body = self.wrap_math_commands(sanitized_body)
        sanitized_body = self.wrap_bare_urls(sanitized_body)
        sanitized_body = self.escape_hashes_in_known_url_commands(sanitized_body)
        return sanitized_body.strip()

    def remove_document_commands(self, body: str) -> str:
        patterns = (
            r"\\documentclass(?:\[[^\]]*\])?\s*\{[^{}]*\}",
            r"\\begin\s*\{document\}",
            r"\\end\s*\{document\}",
            r"\\maketitle",
            r"\\title\s*\{(?:[^{}]|\{[^{}]*\})*\}",
            r"\\author\s*\{(?:[^{}]|\{[^{}]*\})*\}",
            r"\\date\s*\{(?:[^{}]|\{[^{}]*\})*\}",
        )
        sanitized_body = body
        for pattern in patterns:
            sanitized_body = re.sub(pattern, "", sanitized_body, flags=re.DOTALL)
        return sanitized_body

    def remove_dependency_commands(self, body: str) -> str:
        return re.sub(r"\\(?:input|include|subfile)\s*\{(?:[^{}]|\{[^{}]*\})*\}", "", body)

    def remove_bibliography_commands(self, body: str) -> str:
        patterns = (
            r"\\bibliographystyle\s*\{(?:[^{}]|\{[^{}]*\})*\}",
            r"\\bibliography\s*\{(?:[^{}]|\{[^{}]*\})*\}",
            r"\\addbibresource(?:\[[^\]]*\])?\s*\{(?:[^{}]|\{[^{}]*\})*\}",
            r"\\printbibliography\b",
        )
        sanitized_body = body
        for pattern in patterns:
            sanitized_body = re.sub(pattern, "", sanitized_body, flags=re.DOTALL)
        return sanitized_body

    def remove_raw_bibliography_entries(self, body: str) -> str:
        entry_types = (
            "article", "book", "booklet", "conference", "inbook",
            "incollection", "inproceedings", "manual", "mastersthesis",
            "misc", "phdthesis", "proceedings", "techreport",
            "unpublished", "string", "preamble", "comment",
        )
        entry_type_pattern = "|".join(entry_types)
        pattern = re.compile(
            r"^[ \t]*@(?:" + entry_type_pattern + r")\s*([\{\(])",
            flags=re.IGNORECASE | re.MULTILINE,
        )
        output_parts = []
        source_index = 0
        while True:
            match = pattern.search(body, source_index)
            if match is None:
                output_parts.append(body[source_index:])
                break
            opening_character = match.group(1)
            if opening_character == "{":
                closing_character = "}"
            else:
                closing_character = ")"
            opening_index = match.end() - 1
            try:
                entry_content, end_index = self.balanced_reader.read_group(
                    body,
                    opening_index,
                    opening_character,
                    closing_character,
                )
            except ValueError:
                output_parts.append(body[source_index:])
                break
            output_parts.append(body[source_index:match.start()])
            source_index = end_index
        return "".join(output_parts)

    def remove_repeated_global_commands(self, body: str) -> str:
        def table_of_contents_replacement(match: re.Match[str]) -> str:
            if self.seen_table_of_contents:
                return ""
            self.seen_table_of_contents = True
            return match.group(0)

        def list_of_todos_replacement(match: re.Match[str]) -> str:
            if self.seen_list_of_todos:
                return ""
            self.seen_list_of_todos = True
            return match.group(0)

        body = re.sub(r"\\tableofcontents\b", table_of_contents_replacement, body)
        body = re.sub(r"\\listoftodos\b", list_of_todos_replacement, body)
        return body

    def wrap_python_like_blocks(self, body: str) -> str:
        lines = body.splitlines()
        output_lines = []
        index = 0
        protected_environment = ""
        protected_environments = {"minted", "verbatim", "lstlisting", "Verbatim"}
        while index < len(lines):
            line = lines[index]
            begin_match = re.search(r"\\begin\{([^{}]+)\}", line)
            end_match = re.search(r"\\end\{([^{}]+)\}", line)
            if begin_match and begin_match.group(1) in protected_environments:
                protected_environment = begin_match.group(1)
                output_lines.append(line)
                index += 1
                continue
            if protected_environment:
                output_lines.append(line)
                if end_match and end_match.group(1) == protected_environment:
                    protected_environment = ""
                index += 1
                continue
            stripped_line = line.strip()
            if self.is_python_block_start(stripped_line):
                block_lines, next_index = self.collect_python_block(lines, index)
                output_lines.append("\\begin{verbatim}")
                output_lines.extend(block_lines)
                output_lines.append("\\end{verbatim}")
                index = next_index
                continue
            output_lines.append(line)
            index += 1
        return "\n".join(output_lines)

    def is_python_block_start(self, stripped_line: str) -> bool:
        if stripped_line == '"""' or stripped_line == "'''":
            return True
        patterns = (
            r"class\s+[A-Za-z_][A-Za-z0-9_]*(?:\([^)]*\))?\s*:",
            r"def\s+[A-Za-z_][A-Za-z0-9_]*\s*\([^)]*\)\s*(?:->\s*[^:]+)?\s*:",
            r"from\s+[A-Za-z_][A-Za-z0-9_.]*\s+import\s+",
            r"import\s+[A-Za-z_][A-Za-z0-9_.]*",
        )
        return any(re.match(pattern, stripped_line) is not None for pattern in patterns)

    def collect_python_block(self, lines: list[str], start_index: int) -> tuple[list[str], int]:
        first_line = lines[start_index]
        stripped_first_line = first_line.strip()
        if stripped_first_line == '"""' or stripped_first_line == "'''":
            delimiter = stripped_first_line
            block_lines = [first_line]
            index = start_index + 1
            while index < len(lines):
                block_lines.append(lines[index])
                if lines[index].strip() == delimiter:
                    index += 1
                    break
                index += 1
            return block_lines, index
        base_indentation = len(first_line) - len(first_line.lstrip())
        block_lines = [first_line]
        index = start_index + 1
        while index < len(lines):
            current_line = lines[index]
            stripped_current_line = current_line.strip()
            if stripped_current_line == "":
                block_lines.append(current_line)
                index += 1
                continue
            current_indentation = len(current_line) - len(current_line.lstrip())
            if current_line.lstrip().startswith("\\") or current_line.lstrip().startswith("% Source:"):
                break
            if current_indentation <= base_indentation and re.match(r"(?:def|class)\s+", stripped_current_line) is None:
                break
            block_lines.append(current_line)
            index += 1
        return block_lines, index

    def normalize_quoted_text(self, body: str) -> str:
        return re.sub(r'\\"([^"\n]+)\\"', lambda match: "``" + match.group(1) + "''", body)

    def wrap_math_commands(self, body: str) -> str:
        command_names = (
            "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta",
            "eta", "theta", "vartheta", "iota", "kappa", "lambda", "mu", "nu",
            "xi", "pi", "rho", "sigma", "tau", "upsilon", "phi", "varphi",
            "chi", "psi", "omega", "Gamma", "Delta", "Theta", "Lambda", "Xi",
            "Pi", "Sigma", "Upsilon", "Phi", "Psi", "Omega",
        )
        pattern = re.compile(r"\\(" + "|".join(command_names) + r")(?![A-Za-z])")
        return pattern.sub(lambda match: "\\ensuremath{\\" + match.group(1) + "}", body)

    def wrap_bare_urls(self, body: str) -> str:
        pattern = re.compile(r"(?<![\\{A-Za-z0-9_])https?://[^\s{}<>]+")

        def replacement(match: re.Match[str]) -> str:
            url_text = match.group(0)
            trailing_text = ""
            while url_text and url_text[-1] in ".,;:":
                trailing_text = url_text[-1] + trailing_text
                url_text = url_text[:-1]
            escaped_url_text = re.sub(r"(?<!\\)#", r"\\#", url_text)
            return "\\url{" + escaped_url_text + "}" + trailing_text

        return pattern.sub(replacement, body)

    def escape_hashes_in_known_url_commands(self, body: str) -> str:
        command_names = ("seehere", "seeherefooter", "clickurlfooter", "url", "href")
        transformed_body = body
        for command_name in command_names:
            transformed_body = self.escape_hashes_for_command(transformed_body, command_name)
        return transformed_body

    def escape_hashes_for_command(self, body: str, command_name: str) -> str:
        masked_body = self.balanced_reader.mask_comments(body)
        pattern = re.compile(r"\\" + re.escape(command_name) + r"\s*")
        output_parts = []
        source_index = 0
        for match in pattern.finditer(masked_body):
            index = self.balanced_reader.skip_whitespace(masked_body, match.end())
            if index >= len(masked_body) or masked_body[index] != "{":
                continue
            try:
                argument, end_index = self.balanced_reader.read_group(masked_body, index, "{", "}")
            except ValueError:
                continue
            output_parts.append(body[source_index:index + 1])
            output_parts.append(re.sub(r"(?<!\\)#", r"\\#", argument))
            output_parts.append("}")
            source_index = end_index
        output_parts.append(body[source_index:])
        return "".join(output_parts)
