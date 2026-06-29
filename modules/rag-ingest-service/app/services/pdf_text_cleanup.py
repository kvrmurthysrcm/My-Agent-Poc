import re
import unicodedata
from dataclasses import dataclass

from app.core.config import Settings


PAGE_MARKER_RE = re.compile(r"^\[Page\s+\d+\]$", flags=re.IGNORECASE)
PAGE_SPLIT_RE = re.compile(r"(?=^\[Page\s+\d+\]$)", flags=re.IGNORECASE | re.MULTILINE)
PRIVATE_USE_RE = re.compile(r"[\uf000-\uf8ff]")
DEHYPHENATED_LINE_BREAK_RE = re.compile(r"([A-Za-z])-\s*\n\s*([a-z])")
DEHYPHENATED_WORD_WRAP_RE = re.compile(r"\b([A-Za-z]{3,})-\s+([a-z]{2,})\b")
DROP_CAP_RE = re.compile(r"(?m)(^|\n)([A-Z])\s*\n+\s*([a-z][^\n]*)")
WHITESPACE_RE = re.compile(r"\s+")
PAGE_NUMBER_LINE_RE = re.compile(r"^\d{1,4}$")

BOILERPLATE_LINE_PHRASES = (
    "download free ebooks",
    "email newsletter",
    "free ebooks at planet ebook",
    "free ebooks blog",
    "planet ebook.com",
    "subscribe to our free ebooks",
)

JOINED_WORD_REPAIRS = (
    (re.compile(r"\bandpresented\b"), "and presented"),
    (re.compile(r"\bhadwarned\b"), "had warned"),
    (re.compile(r"\bthreequarters\b"), "three quarters"),
)


@dataclass(frozen=True)
class CleanupStats:
    repeated_lines_removed: int = 0
    boilerplate_lines_removed: int = 0
    page_number_lines_removed: int = 0
    joined_word_repairs: int = 0


class PdfTextCleanupService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def clean(self, text: str) -> tuple[str, CleanupStats]:
        if not text:
            return text, CleanupStats()

        cleaned = unicodedata.normalize("NFKC", text) if self.settings.pdf_normalize_unicode else text
        if self.settings.pdf_remove_private_use_glyphs:
            cleaned = PRIVATE_USE_RE.sub("", cleaned)

        repeated_lines = self._repeated_page_lines(cleaned) if self.settings.pdf_remove_repeated_headers_footers else set()
        cleaned, stats = self._clean_page_lines(cleaned, repeated_lines)

        if self.settings.pdf_dehyphenate_line_breaks:
            cleaned = DEHYPHENATED_LINE_BREAK_RE.sub(r"\1\2", cleaned)
            # Some extractors or CSV exports normalize wrapped words to
            # "gentle- men" instead of keeping the original line break. This
            # catches common PDF word-wrap remnants like "mer- ry" while
            # avoiding short forms such as "re- used", where joining would be
            # more ambiguous.
            cleaned = DEHYPHENATED_WORD_WRAP_RE.sub(r"\1\2", cleaned)

        if self.settings.pdf_repair_drop_caps:
            # Some PDFs render a decorative first letter as its own block:
            # "M" on one line and "arley was dead" on the next. If left as-is,
            # section detection treats "M" as a heading and Graph RAG sees
            # "arley" as an entity. Merge that single-letter drop cap back into
            # the following lowercase line.
            cleaned = DROP_CAP_RE.sub(r"\1\2\3", cleaned)

        if self.settings.pdf_repair_joined_words:
            cleaned, joined_word_repairs = _repair_joined_words(cleaned)
            stats = CleanupStats(
                repeated_lines_removed=stats.repeated_lines_removed,
                boilerplate_lines_removed=stats.boilerplate_lines_removed,
                page_number_lines_removed=stats.page_number_lines_removed,
                joined_word_repairs=joined_word_repairs,
            )

        return cleaned.strip(), stats

    def _clean_page_lines(self, text: str, repeated_lines: set[str]) -> tuple[str, CleanupStats]:
        pages = _split_pages(text)
        page_count = len(pages)
        cleaned_pages: list[str] = []
        repeated_removed = 0
        boilerplate_removed = 0
        page_number_removed = 0

        for page in pages:
            lines: list[str] = []
            for raw_line in page.splitlines():
                line = raw_line.strip()
                if not line:
                    lines.append("")
                    continue
                if PAGE_MARKER_RE.fullmatch(line):
                    lines.append(line)
                    continue
                normalized = _normalize_line_key(line)
                if normalized in repeated_lines:
                    repeated_removed += 1
                    continue
                if self.settings.pdf_remove_boilerplate_lines and _is_boilerplate_line(normalized):
                    boilerplate_removed += 1
                    continue
                if self.settings.pdf_remove_page_number_lines and _is_page_number_line(normalized, page_count):
                    # PDF page numbers are often extracted as their own line.
                    # If retained, paragraph cleanup later makes them appear
                    # inline, e.g. "Marley's 15 pigtail", which pollutes
                    # embeddings and Graph RAG extraction.
                    page_number_removed += 1
                    continue
                lines.append(line)
            cleaned_pages.append(_collapse_blank_lines(lines))

        return "\n\n".join(page for page in cleaned_pages if page), CleanupStats(
            repeated_lines_removed=repeated_removed,
            boilerplate_lines_removed=boilerplate_removed,
            page_number_lines_removed=page_number_removed,
        )

    def _repeated_page_lines(self, text: str) -> set[str]:
        page_lines: dict[str, set[int]] = {}
        pages = _split_pages(text)
        page_count = len(pages)
        if page_count < 3:
            return set()

        for page_index, page in enumerate(pages):
            for raw_line in page.splitlines():
                line = raw_line.strip()
                if not line or PAGE_MARKER_RE.fullmatch(line):
                    continue
                normalized = _normalize_line_key(line)
                if _is_boilerplate_line(normalized):
                    continue
                if not _can_be_running_header_footer(normalized):
                    continue
                page_lines.setdefault(normalized, set()).add(page_index)

        min_pages = max(3, int(page_count * 0.25))
        return {line for line, indexes in page_lines.items() if len(indexes) >= min_pages}


def _split_pages(text: str) -> list[str]:
    pages = [page.strip() for page in PAGE_SPLIT_RE.split(text) if page.strip()]
    return pages or [text]


def _normalize_line_key(line: str) -> str:
    return WHITESPACE_RE.sub(" ", line).strip().lower()


def _collapse_blank_lines(lines: list[str]) -> str:
    collapsed: list[str] = []
    previous_blank = False
    for line in lines:
        is_blank = not line
        if is_blank and previous_blank:
            continue
        collapsed.append(line)
        previous_blank = is_blank
    return "\n".join(collapsed).strip()


def _can_be_running_header_footer(line: str) -> bool:
    if not line or len(line) > 80:
        return False
    if line.isdigit():
        return True
    return len(line.split()) <= 8


def _is_boilerplate_line(line: str) -> bool:
    return any(phrase in line for phrase in BOILERPLATE_LINE_PHRASES)


def _is_page_number_line(line: str, page_count: int) -> bool:
    if not PAGE_NUMBER_LINE_RE.fullmatch(line):
        return False
    number = int(line)
    return 1 <= number <= max(page_count + 5, 10)


def _repair_joined_words(text: str) -> tuple[str, int]:
    repair_count = 0
    repaired = text
    for pattern, replacement in JOINED_WORD_REPAIRS:
        repaired, count = pattern.subn(replacement, repaired)
        repair_count += count
    return repaired, repair_count
