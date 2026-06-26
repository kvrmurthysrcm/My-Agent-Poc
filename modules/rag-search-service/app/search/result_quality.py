import re


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")
PAGE_MARKER_RE = re.compile(r"\[Page\s+\d+\]", flags=re.IGNORECASE)
ROMAN_RE = re.compile(r"^[ivxlcdm]+$", flags=re.IGNORECASE)
BOILERPLATE_PHRASES = (
    "all rights reserved",
    "copyright",
    "download free ebooks",
    "executive officer",
    "free ebooks at",
    "isbn",
    "planet ebook",
    "publications division",
    "printed at",
    "publisher",
    "tirumala tirupati devasthanams press",
)


def is_searchable_result_text(text: str, keep_numeric_table_chunks: bool = True, min_alpha_ratio: float = 0.45) -> bool:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return False

    tokens = [token for token in TOKEN_RE.findall(normalized) if not ROMAN_RE.fullmatch(token)]
    meaningful_tokens = [token for token in tokens if len(token.strip("'-")) >= 3]

    if len(meaningful_tokens) < 5:
        return False
    if is_short_boilerplate_text(normalized):
        return False

    alpha_chars = sum(1 for char in normalized if char.isalpha())
    visible_chars = sum(1 for char in normalized if not char.isspace())
    if visible_chars and alpha_chars / visible_chars < min_alpha_ratio and not (
        keep_numeric_table_chunks and _is_numeric_table_heavy(normalized)
    ):
        return False

    mojibake_chars = sum(normalized.count(marker) for marker in ("Ãƒ", "Ã‚", "Ã¢Â€", "ï¿½"))
    if visible_chars and mojibake_chars / visible_chars > 0.08:
        return False

    return True


def is_searchable_chunk_metadata(metadata: dict | None) -> bool:
    if not metadata:
        return True
    return metadata.get("searchable") is not False and metadata.get("quality") != "filtered"


def clean_result_text(text: str) -> str:
    without_page_markers = PAGE_MARKER_RE.sub(" ", text or "")
    return re.sub(r"\s+", " ", without_page_markers).strip()


def is_short_boilerplate_text(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    lower = normalized.lower()
    tokens = [token for token in TOKEN_RE.findall(normalized) if not ROMAN_RE.fullmatch(token)]
    meaningful_tokens = [token for token in tokens if len(token.strip("'-")) >= 3]
    if any(phrase in lower for phrase in BOILERPLATE_PHRASES) and len(meaningful_tokens) < 60:
        return True
    if "[page" in lower:
        cleaned = clean_result_text(normalized)
        cleaned_tokens = [token for token in TOKEN_RE.findall(cleaned) if not ROMAN_RE.fullmatch(token)]
        cleaned_meaningful_tokens = [token for token in cleaned_tokens if len(token.strip("'-")) >= 3]
        return len(cleaned_meaningful_tokens) < 5
    return False


def _is_numeric_table_heavy(text: str) -> bool:
    visible_chars = [char for char in text if not char.isspace()]
    if not visible_chars:
        return False
    digit_chars = sum(1 for char in visible_chars if char.isdigit())
    table_separators = sum(text.count(marker) for marker in ("|", "\t", "  ", ",", ";", ":"))
    code_like_tokens = len(re.findall(r"\b[A-Z]{1,6}[-_/]?\d{2,}\b|\b\d+[A-Z]+[-_/]?\d*\b", text))
    return digit_chars / len(visible_chars) >= 0.25 and (table_separators >= 3 or code_like_tokens >= 2)
