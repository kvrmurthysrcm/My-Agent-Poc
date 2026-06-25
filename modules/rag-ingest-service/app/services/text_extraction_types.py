from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    parser_name: str
    page_count: int | None
    metadata: dict
