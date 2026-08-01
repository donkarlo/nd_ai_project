from pathlib import Path
from project_file_system import ProjectFileSystem


class DependencyResolver:
    def __init__(self, source_directory: Path, project_file_system: ProjectFileSystem) -> None:
        self.source_directory = source_directory.resolve()
        self.project_root = self.source_directory.parent.resolve()
        self.project_file_system = project_file_system
        self.tex_paths = self.create_tex_path_index()
        self.paths_by_name = self.create_paths_by_name_index()

    def create_tex_path_index(self) -> tuple[Path, ...]:
        paths = []
        for root_directory in (self.source_directory, self.project_root):
            for path in root_directory.rglob("*.tex"):
                if not self.project_file_system.should_skip_path(path):
                    paths.append(path.resolve())
        unique_paths = sorted(set(paths), key=lambda path: path.as_posix().casefold())
        return tuple(unique_paths)

    def create_paths_by_name_index(self) -> dict[str, tuple[Path, ...]]:
        index = {}
        mutable_index = {}
        for path in self.tex_paths:
            for key in (path.name.casefold(), path.stem.casefold()):
                mutable_index.setdefault(key, []).append(path)
        for key, paths in mutable_index.items():
            index[key] = tuple(paths)
        return index

    def resolve(self, reference: str, including_path: Path) -> Path | None:
        normalized_reference = self.normalize_reference(reference)
        if not normalized_reference:
            return None
        reference_path = Path(normalized_reference).expanduser()
        if reference_path.suffix and reference_path.suffix.casefold() != ".tex":
            return None
        candidate_paths = []
        if reference_path.is_absolute():
            candidate_paths.append(reference_path)
        else:
            candidate_paths.extend((
                including_path.parent / reference_path,
                self.source_directory / reference_path,
                self.project_root / reference_path,
            ))
        expanded_candidates = []
        for candidate_path in candidate_paths:
            if candidate_path.suffix.casefold() == ".tex":
                expanded_candidates.append(candidate_path)
            elif candidate_path.suffix == "":
                expanded_candidates.append(candidate_path.with_suffix(".tex"))
        for candidate_path in expanded_candidates:
            if candidate_path.is_file():
                return candidate_path.resolve()
        suffix_match = self.find_by_suffix(reference_path)
        if suffix_match is not None:
            return suffix_match
        name_key = reference_path.name.casefold()
        if name_key in self.paths_by_name and len(self.paths_by_name[name_key]) == 1:
            return self.paths_by_name[name_key][0]
        stem_key = reference_path.stem.casefold()
        if stem_key in self.paths_by_name and len(self.paths_by_name[stem_key]) == 1:
            return self.paths_by_name[stem_key][0]
        return None

    def normalize_reference(self, reference: str) -> str:
        normalized_reference = reference.strip().strip('"').strip("'")
        if normalized_reference.startswith("\\srcpath{") and normalized_reference.endswith("}"):
            normalized_reference = normalized_reference[len("\\srcpath{"):-1]
        if normalized_reference.startswith("\\input{") and normalized_reference.endswith("}"):
            normalized_reference = normalized_reference[len("\\input{"):-1]
        if "\\" in normalized_reference:
            return ""
        return normalized_reference

    def find_by_suffix(self, reference_path: Path) -> Path | None:
        normalized_reference_path = reference_path
        if normalized_reference_path.suffix == "":
            normalized_reference_path = normalized_reference_path.with_suffix(".tex")
        reference_parts = tuple(part.casefold() for part in normalized_reference_path.parts)
        if not reference_parts:
            return None
        matches = []
        for path in self.tex_paths:
            path_parts = tuple(part.casefold() for part in path.parts)
            if len(path_parts) >= len(reference_parts) and path_parts[-len(reference_parts):] == reference_parts:
                matches.append(path)
            elif path.stem.casefold() == reference_path.stem.casefold():
                matches.append(path)
        unique_matches = sorted(set(matches), key=lambda path: path.as_posix().casefold())
        if len(unique_matches) == 1:
            return unique_matches[0]
        return None
