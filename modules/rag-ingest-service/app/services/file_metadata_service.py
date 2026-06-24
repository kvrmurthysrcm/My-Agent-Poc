from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile
import xml.etree.ElementTree as ET

from app.schemas.ingest_request import IngestMetadata


@dataclass(frozen=True)
class ExtractedFileMetadata:
    title: str | None = None
    description: str | None = None
    author: str | None = None
    language: str | None = None
    publisher: str | None = None
    published_date: datetime | None = None
    created_date_from_file: datetime | None = None
    raw_metadata: dict | None = None


class FileMetadataService:
    def extract(self, path: Path, extension: str) -> ExtractedFileMetadata:
        if extension == ".epub":
            return self._extract_epub_metadata(path)
        if extension == ".pdf":
            return self._extract_pdf_metadata(path)
        if extension == ".docx":
            return self._extract_docx_metadata(path)
        return ExtractedFileMetadata()

    def merge_with_request_metadata(
        self,
        request_metadata: IngestMetadata,
        file_metadata: ExtractedFileMetadata,
        fallback_title: str,
    ) -> IngestMetadata:
        raw_metadata = file_metadata.raw_metadata or {}
        merged_custom_metadata = dict(request_metadata.custom_metadata)
        if raw_metadata:
            merged_custom_metadata.setdefault("file_metadata", raw_metadata)

        return request_metadata.model_copy(
            update={
                "title": request_metadata.title or file_metadata.title or fallback_title,
                "description": request_metadata.description or file_metadata.description,
                "author": request_metadata.author or file_metadata.author,
                "language": request_metadata.language or file_metadata.language or "English",
                "publisher": request_metadata.publisher or file_metadata.publisher,
                "published_date": request_metadata.published_date or file_metadata.published_date,
                "created_date_from_file": request_metadata.created_date_from_file
                or file_metadata.created_date_from_file,
                "custom_metadata": merged_custom_metadata,
            }
        )

    def _extract_epub_metadata(self, path: Path) -> ExtractedFileMetadata:
        with ZipFile(path) as archive:
            rootfile = self._find_epub_rootfile(archive)
            if not rootfile:
                return ExtractedFileMetadata()
            root = ET.fromstring(archive.read(rootfile))
            values = self._read_epub_metadata_values(root)
            return ExtractedFileMetadata(
                title=values.get("title"),
                description=values.get("description"),
                author=values.get("creator"),
                language=values.get("language"),
                publisher=values.get("publisher"),
                published_date=_parse_datetime(values.get("date")),
                created_date_from_file=_parse_datetime(values.get("date")),
                raw_metadata=values,
            )

    def _extract_pdf_metadata(self, path: Path) -> ExtractedFileMetadata:
        try:
            from pypdf import PdfReader
        except ImportError:
            return ExtractedFileMetadata()

        reader = PdfReader(str(path))
        metadata = dict(reader.metadata or {})
        cleaned = {str(key).lstrip("/").lower(): str(value) for key, value in metadata.items() if value}
        return ExtractedFileMetadata(
            title=cleaned.get("title"),
            author=cleaned.get("author"),
            raw_metadata=cleaned,
        )

    def _extract_docx_metadata(self, path: Path) -> ExtractedFileMetadata:
        try:
            from docx import Document
        except ImportError:
            return ExtractedFileMetadata()

        props = Document(str(path)).core_properties
        raw = {
            "title": props.title,
            "author": props.author,
            "subject": props.subject,
            "keywords": props.keywords,
            "created": props.created.isoformat() if props.created else None,
            "modified": props.modified.isoformat() if props.modified else None,
        }
        raw = {key: value for key, value in raw.items() if value}
        return ExtractedFileMetadata(
            title=props.title or None,
            description=props.subject or None,
            author=props.author or None,
            created_date_from_file=props.created,
            raw_metadata=raw,
        )

    def _find_epub_rootfile(self, archive: ZipFile) -> str | None:
        try:
            container_xml = archive.read("META-INF/container.xml")
        except KeyError:
            return None
        root = ET.fromstring(container_xml)
        for element in root.iter():
            if element.tag.endswith("rootfile"):
                return element.attrib.get("full-path")
        return None

    def _read_epub_metadata_values(self, root: ET.Element) -> dict[str, str]:
        values: dict[str, str] = {}
        for element in root.iter():
            tag = element.tag.rsplit("}", 1)[-1].lower()
            if tag in {"title", "creator", "language", "publisher", "date", "description"}:
                text = (element.text or "").strip()
                if text and tag not in values:
                    values[tag] = text
        return values


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        try:
            return datetime.fromisoformat(normalized[:10])
        except ValueError:
            return None
