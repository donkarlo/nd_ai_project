from typing import List


class YamlNaturalizer:
    def __init__(self):
        pass

    def naturalize(self, source_path: str, yaml_text: str) -> str:
        lines = yaml_text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
        out_lines: List[str] = []
        out_lines.append(f"source_path: {source_path}")

        current_keys: List[str] = []

        for raw_line in lines:
            if not raw_line.strip():
                continue

            indentation_spaces = len(raw_line) - len(raw_line.lstrip(" "))
            level = indentation_spaces // 2

            stripped = raw_line.strip()
            if ":" not in stripped:
                continue

            key_part, value_part = stripped.split(":", 1)
            key = key_part.strip()
            value = value_part.strip()

            if level < 0:
                level = 0

            while len(current_keys) > level:
                current_keys.pop()

            if key:
                if len(current_keys) == level:
                    current_keys.append(key)

            if value:
                key_path = ".".join(current_keys)
                out_lines.append(f"{key_path} = {value}")

        return "\n".join(out_lines).strip()
