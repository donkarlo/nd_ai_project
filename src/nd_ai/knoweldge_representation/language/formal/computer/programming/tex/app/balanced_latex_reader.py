class BalancedLatexReader:
    def read_group(self, text: str, opening_index: int, opening_character: str, closing_character: str) -> tuple[str, int]:
        if opening_index >= len(text) or text[opening_index] != opening_character:
            raise ValueError("The opening character was not found at the requested position.")
        depth = 0
        index = opening_index
        escaped = False
        while index < len(text):
            character = text[index]
            if escaped:
                escaped = False
                index += 1
                continue
            if character == "\\":
                escaped = True
                index += 1
                continue
            if character == opening_character:
                depth += 1
            elif character == closing_character:
                depth -= 1
                if depth == 0:
                    return text[opening_index + 1:index], index + 1
            index += 1
        raise ValueError("An unbalanced LaTeX group was found.")

    def skip_whitespace(self, text: str, index: int) -> int:
        while index < len(text) and text[index].isspace():
            index += 1
        return index

    def read_command_name(self, text: str, slash_index: int) -> tuple[str, int]:
        index = slash_index + 1
        if index >= len(text):
            return "", index
        if text[index].isalpha() or text[index] == "@":
            start_index = index
            while index < len(text) and (text[index].isalpha() or text[index] == "@"):
                index += 1
            return text[start_index:index], index
        return text[index], index + 1

    def mask_comments(self, text: str) -> str:
        characters = list(text)
        index = 0
        while index < len(characters):
            if characters[index] == "%" and not self.is_escaped(text, index):
                while index < len(characters) and characters[index] != "\n":
                    characters[index] = " "
                    index += 1
            else:
                index += 1
        return "".join(characters)

    def is_escaped(self, text: str, index: int) -> bool:
        backslash_count = 0
        index -= 1
        while index >= 0 and text[index] == "\\":
            backslash_count += 1
            index -= 1
        return backslash_count % 2 == 1
