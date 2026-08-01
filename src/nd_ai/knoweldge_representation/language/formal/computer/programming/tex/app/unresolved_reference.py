from dataclasses import dataclass


@dataclass(frozen=True)
class UnresolvedReference:
    reference: str
    source_path: str
    reference_kind: str
