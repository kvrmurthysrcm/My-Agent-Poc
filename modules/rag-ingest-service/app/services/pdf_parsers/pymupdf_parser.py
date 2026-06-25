from pathlib import Path

from app.services.text_extraction_types import ExtractionResult


class PyMuPdfParser:
    parser_name = "pymupdf"

    def extract(self, path: Path) -> ExtractionResult:
        try:
            import fitz
        except ImportError as exc:
            raise RuntimeError("pymupdf is required for PDF extraction") from exc

        pages: list[str] = []
        metadata: dict = {}
        with fitz.open(path) as document:
            metadata = dict(document.metadata or {})
            for index, page in enumerate(document, start=1):
                pages.append(f"[Page {index}]\n{page.get_text('text') or ''}")
            page_count = document.page_count

        return ExtractionResult(
            text="\n\n".join(pages),
            parser_name=self.parser_name,
            page_count=page_count,
            metadata={"pdf_metadata": metadata},
        )
