from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExtractionResult:
    text: str
    parser_name: str
    page_count: int | None
    metadata: dict


class TextExtractionService:
    def extract(self, path: Path, extension: str) -> ExtractionResult:
        if extension == ".txt":
            return self._extract_txt(path)
        if extension == ".pdf":
            return self._extract_pdf(path)
        if extension == ".docx":
            return self._extract_docx(path)
        raise ValueError(f"Unsupported extraction extension: {extension}")

    def _extract_txt(self, path: Path) -> ExtractionResult:
        text = path.read_text(encoding="utf-8", errors="replace")
        return ExtractionResult(text=text, parser_name="plain_text", page_count=None, metadata={})

    def _extract_pdf(self, path: Path) -> ExtractionResult:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required for PDF extraction") from exc

        reader = PdfReader(str(path))
        pages = [page.extract_text() or "" for page in reader.pages]
        text = "\n\n".join(f"[Page {index + 1}]\n{page_text}" for index, page_text in enumerate(pages))
        return ExtractionResult(
            text=text,
            parser_name="pypdf",
            page_count=len(reader.pages),
            metadata={"pdf_metadata": dict(reader.metadata or {})},
        )

    def _extract_docx(self, path: Path) -> ExtractionResult:
        try:
            from docx import Document
        except ImportError as exc:
            raise RuntimeError("python-docx is required for DOCX extraction") from exc

        document = Document(str(path))
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        return ExtractionResult(text="\n\n".join(parts), parser_name="python-docx", page_count=None, metadata={})
