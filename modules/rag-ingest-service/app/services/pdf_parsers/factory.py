from app.core.config import Settings
from app.services.pdf_parsers.base import PdfParser
from app.services.pdf_parsers.pymupdf_parser import PyMuPdfParser
from app.services.pdf_parsers.pypdf_parser import PyPdfParser


class PdfParserFactory:
    @staticmethod
    def build(settings: Settings) -> PdfParser:
        if settings.pdf_parser == "pymupdf":
            return PyMuPdfParser()
        if settings.pdf_parser == "pypdf":
            return PyPdfParser()
        raise ValueError(f"Unsupported PDF parser: {settings.pdf_parser}")
