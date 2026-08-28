from dataclasses import dataclass


@dataclass(frozen=True)
class DocumentClassOption:
    key: str
    description: str
    supports_chapter: bool
