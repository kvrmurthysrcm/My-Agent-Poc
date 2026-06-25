from pathlib import Path

from app.services.text_extraction_types import ExtractionResult


class PyPdfParser:
    parser_name = "pypdf"

    def extract(self, path: Path) -> ExtractionResult:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required for PDF extraction") from exc

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(f"[Page {index + 1}]\n{page_text}" for index, page_text in enumerate(pages))
        return ExtractionResult(
            text=text,
            parser_name=self.parser_name,
            page_count=len(reader.pages),
            metadata={"pdf_metadata": dict(reader.metadata or {})},
        )
