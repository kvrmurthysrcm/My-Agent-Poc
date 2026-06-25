from pathlib import Path
from typing import Protocol

from app.services.text_extraction_types import ExtractionResult


class PdfParser(Protocol):
    parser_name: str

    def extract(self, path: Path) -> ExtractionResult:
        ...
