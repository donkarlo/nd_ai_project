from dataclasses import dataclass


@dataclass(frozen=True)
class HeadingOption:
    command: str
    description: str
