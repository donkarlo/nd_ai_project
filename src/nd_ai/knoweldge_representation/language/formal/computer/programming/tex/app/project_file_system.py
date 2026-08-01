from pathlib import Path
from source_file import SourceFile


class ProjectFileSystem:
    def __init__(self) -> None:
        self.generated_file_names = {
            "merged_project.tex",
        }
        self.excluded_directory_names = {
            ".git",
            ".idea",
            "__pycache__",
            "out",
            "build",
            "dist",
            "merged_latex_output",
        }

    def read_text(self, path: Path) -> str:
        encodings = ("utf-8-sig", "utf-8", "latin-1")
        for encoding in encodings:
            try:
                return path.read_text(encoding=encoding)
            except UnicodeDecodeError:
                continue
        return path.read_text(errors="replace")

    def discover_tex_files(self, source_directory: Path) -> list[SourceFile]:
        source_files = []
        for path in source_directory.rglob("*.tex"):
            if self.should_skip_path(path):
                continue
            relative_path = path.relative_to(source_directory).as_posix()
            source_files.append(SourceFile(path.resolve(), relative_path, self.read_text(path)))
        source_files.sort(key=self.source_file_sort_key)
        return source_files

    def should_skip_path(self, path: Path) -> bool:
        if path.name in self.generated_file_names:
            return True
        for part in path.parts:
            if part in self.excluded_directory_names:
                return True
        return False

    def source_file_sort_key(self, source_file: SourceFile) -> tuple[int, tuple[str, ...], int, str]:
        relative_path = Path(source_file.relative_path)
        directory_parts = tuple(part.casefold() for part in relative_path.parent.parts if part != ".")
        file_stem = relative_path.stem.casefold()
        preferred_file = 1
        if relative_path.parent.name and file_stem == relative_path.parent.name.casefold():
            preferred_file = 0
        root_file = 1
        if relative_path.parent == Path("."):
            root_file = 0
        return root_file, directory_parts, preferred_file, file_stem

    def write_text(self, path: Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
