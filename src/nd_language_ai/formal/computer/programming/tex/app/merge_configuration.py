from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class MergeConfiguration:
    source_directory: Path
    document_class: str
    starting_heading: str
    output_tex_path: Path
    bibliography_path: Path
