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
                pages.append(f"[Page {index}]\n{self._extract_page_text(page)}")
            page_count = document.page_count

        return ExtractionResult(
            text="\n\n".join(pages),
            parser_name=self.parser_name,
            page_count=page_count,
            metadata={"pdf_metadata": metadata},
        )

    def _extract_page_text(self, page) -> str:
        blocks = page.get_text("blocks") or []
        text_blocks = []
        for block in sorted(blocks, key=lambda item: (round(item[1], 1), round(item[0], 1))):
            if len(block) < 5:
                continue
            text = str(block[4]).strip()
            if text:
                text_blocks.append(text)
        if text_blocks:
            return "\n\n".join(text_blocks)
        return page.get_text("text") or ""
