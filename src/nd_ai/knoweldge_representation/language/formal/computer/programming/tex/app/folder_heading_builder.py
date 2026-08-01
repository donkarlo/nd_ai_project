from pathlib import Path
from heading_transformer import HeadingTransformer


class FolderHeadingBuilder:
    def __init__(self, source_directory: Path, heading_transformer: HeadingTransformer) -> None:
        self.source_directory = source_directory.resolve()
        self.heading_transformer = heading_transformer
        self.emitted_directories = set()

    def build_for_path(self, source_path: Path) -> str:
        try:
            relative_parent = source_path.resolve().parent.relative_to(self.source_directory)
        except ValueError:
            return ""
        if relative_parent == Path("."):
            return ""
        headings = []
        accumulated_path = Path()
        for depth, part in enumerate(relative_parent.parts, start=1):
            accumulated_path = accumulated_path / part
            accumulated_key = accumulated_path.as_posix().casefold()
            if accumulated_key in self.emitted_directories:
                continue
            self.emitted_directories.add(accumulated_key)
            headings.append(self.heading_transformer.render_folder_heading(depth, part))
        return "\n\n".join(headings)

    def folder_depth_for_path(self, source_path: Path) -> int:
        try:
            relative_parent = source_path.resolve().parent.relative_to(self.source_directory)
        except ValueError:
            return 0
        if relative_parent == Path("."):
            return 0
        return len(relative_parent.parts)
