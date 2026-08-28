from dataclasses import dataclass
from source_file import SourceFile


@dataclass(frozen=True)
class ParsedDocument:
    source_file: SourceFile
    preamble: str
    body: str
    title: str
    preamble_dependencies: tuple[str, ...]
    body_dependencies: tuple[str, ...]
    bibliography_references: tuple[str, ...]
    bibliography_style: str
    is_full_document: bool
    is_preamble_fragment: bool
