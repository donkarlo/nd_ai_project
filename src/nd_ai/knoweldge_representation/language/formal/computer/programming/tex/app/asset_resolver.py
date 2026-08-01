import re
from pathlib import Path
from balanced_latex_reader import BalancedLatexReader


class AssetResolver:
    def __init__(self, source_directory: Path, balanced_reader: BalancedLatexReader) -> None:
        self.source_directory = source_directory.resolve()
        self.project_root = self.source_directory.parent.resolve()
        self.balanced_reader = balanced_reader
        self.asset_paths = self.create_asset_index()
        self.resolved_count = 0
        self.unresolved_count = 0
        self.warnings = []
        self.warning_keys = set()

    def create_asset_index(self) -> tuple[Path, ...]:
        supported_suffixes = {".pdf", ".png", ".jpg", ".jpeg", ".svg", ".eps", ".webp"}
        paths = []
        for path in self.project_root.rglob("*"):
            if path.is_file() and path.suffix.casefold() in supported_suffixes:
                paths.append(path.resolve())
        return tuple(sorted(paths, key=lambda item: item.as_posix().casefold()))

    def transform(self, body: str, source_path: Path) -> str:
        transformed_body = body
        transformed_body = self.transform_command(transformed_body, source_path, "includegraphics", "ProjectSafeIncludeGraphics", (".pdf", ".png", ".jpg", ".jpeg", ".eps"))
        transformed_body = self.transform_command(transformed_body, source_path, "includepdf", "ProjectSafeIncludePdf", (".pdf",))
        transformed_body = self.transform_command(transformed_body, source_path, "includesvg", "ProjectSafeIncludeSvg", (".svg",))
        return transformed_body

    def transform_command(self, body: str, source_path: Path, command_name: str, safe_command_name: str, preferred_suffixes: tuple[str, ...]) -> str:
        masked_body = self.balanced_reader.mask_comments(body)
        pattern = re.compile(r"\\" + re.escape(command_name) + r"\s*")
        output_parts = []
        source_index = 0
        for match in pattern.finditer(masked_body):
            index = self.balanced_reader.skip_whitespace(masked_body, match.end())
            option_text = ""
            if index < len(masked_body) and masked_body[index] == "[":
                try:
                    options, index = self.balanced_reader.read_group(masked_body, index, "[", "]")
                    option_text = "[" + options + "]"
                except ValueError:
                    continue
                index = self.balanced_reader.skip_whitespace(masked_body, index)
            if index >= len(masked_body) or masked_body[index] != "{":
                continue
            try:
                raw_reference, end_index = self.balanced_reader.read_group(masked_body, index, "{", "}")
            except ValueError:
                continue
            output_parts.append(body[source_index:match.start()])
            resolved_reference = self.resolve_asset_reference(raw_reference, source_path, preferred_suffixes)
            if resolved_reference is None:
                self.unresolved_count += 1
                self.add_warning(f"Asset was not found: {raw_reference.strip()} from {source_path.as_posix()}", "asset:" + raw_reference.strip())
                safe_reference = self.escape_placeholder_text(raw_reference.strip())
                replacement = f"\\ProjectMissingAsset{{{safe_reference}}}"
            else:
                self.resolved_count += 1
                replacement = f"\\{safe_command_name}{option_text}{{{resolved_reference}}}"
            output_parts.append(replacement)
            source_index = end_index
        output_parts.append(body[source_index:])
        return "".join(output_parts)


    def add_warning(self, warning: str, warning_key: str) -> None:
        if warning_key not in self.warning_keys:
            self.warning_keys.add(warning_key)
            self.warnings.append(warning)

    def resolve_asset_reference(self, raw_reference: str, source_path: Path, preferred_suffixes: tuple[str, ...]) -> str | None:
        normalized_reference = self.normalize_reference(raw_reference)
        candidate_paths = []
        if normalized_reference:
            reference_path = Path(normalized_reference).expanduser()
            if reference_path.is_absolute():
                candidate_paths.append(reference_path)
            else:
                candidate_paths.extend((
                    source_path.parent / reference_path,
                    self.source_directory / reference_path,
                    self.project_root / reference_path,
                ))
            for candidate_path in list(candidate_paths):
                if candidate_path.suffix == "":
                    for suffix in preferred_suffixes:
                        candidate_paths.append(candidate_path.with_suffix(suffix))
            for candidate_path in candidate_paths:
                if candidate_path.is_file():
                    return self.relative_output_reference(candidate_path.resolve())
        basename = self.extract_basename(raw_reference)
        matches = []
        for path in self.asset_paths:
            if path.name.casefold() == basename.casefold():
                matches.append(path)
            elif Path(basename).suffix == "" and path.stem.casefold() == basename.casefold() and path.suffix.casefold() in preferred_suffixes:
                matches.append(path)
        if not matches:
            return None
        matches.sort(key=lambda path: self.asset_match_score(path, source_path, preferred_suffixes))
        return self.relative_output_reference(matches[0])

    def normalize_reference(self, raw_reference: str) -> str:
        normalized_reference = raw_reference.strip()
        normalized_reference = re.sub(r"\\[A-Za-z@]+", "", normalized_reference)
        normalized_reference = normalized_reference.strip().strip('"').strip("'")
        return normalized_reference

    def extract_basename(self, raw_reference: str) -> str:
        normalized_reference = self.normalize_reference(raw_reference)
        if normalized_reference:
            return Path(normalized_reference).name
        tokens = re.findall(r"[A-Za-z0-9_.-]+", raw_reference)
        if tokens:
            return tokens[-1]
        return raw_reference.strip()

    def asset_match_score(self, path: Path, source_path: Path, preferred_suffixes: tuple[str, ...]) -> tuple[int, int, str]:
        if path.suffix.casefold() in preferred_suffixes:
            suffix_score = preferred_suffixes.index(path.suffix.casefold())
        else:
            suffix_score = len(preferred_suffixes)
        shared_parts = len(set(path.parent.parts) & set(source_path.parent.parts))
        return suffix_score, -shared_parts, path.as_posix().casefold()

    def relative_output_reference(self, path: Path) -> str:
        try:
            return path.relative_to(self.source_directory).as_posix()
        except ValueError:
            return Path("..", path.relative_to(self.project_root)).as_posix()

    def escape_placeholder_text(self, text: str) -> str:
        replacements = {
            "\\": "/",
            "{": "(",
            "}": ")",
            "%": "\\%",
            "#": "\\#",
            "_": "\\_",
            "&": "\\&",
        }
        escaped_text = text
        for old_text, new_text in replacements.items():
            escaped_text = escaped_text.replace(old_text, new_text)
        return escaped_text
