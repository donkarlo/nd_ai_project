from pathlib import Path
from project_file_system import ProjectFileSystem


class OutputWriter:
    def __init__(self, project_file_system: ProjectFileSystem) -> None:
        self.project_file_system = project_file_system

    def write(self, output_path: Path, tex_content: str) -> None:
        self.project_file_system.write_text(output_path, tex_content)
