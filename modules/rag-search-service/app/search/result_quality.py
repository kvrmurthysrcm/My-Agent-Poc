import re


TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")
PAGE_MARKER_RE = re.compile(r"\[Page\s+\d+\]", flags=re.IGNORECASE)
ROMAN_RE = re.compile(r"^[ivxlcdm]+$", flags=re.IGNORECASE)
BOILERPLATE_PHRASES = (
    "all rights reserved",
    "download free ebooks",
    "executive officer",
    "free ebooks at",
    "planet ebook",
    "publications division",
    "printed at",
    "tirumala tirupati devasthanams press",
)


def is_searchable_result_text(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text or "").strip()
    if not normalized:
        return False

    tokens = [token for token in TOKEN_RE.findall(normalized) if not ROMAN_RE.fullmatch(token)]
    meaningful_tokens = [token for token in tokens if len(token.strip("'-")) >= 3]
    lower = normalized.lower()

    if len(meaningful_tokens) < 5:
        return False
    if is_short_boilerplate_text(normalized):
        return False

    alpha_chars = sum(1 for char in normalized if char.isalpha())
    visible_chars = sum(1 for char in normalized if not char.isspace())
    if visible_chars and alpha_chars / visible_chars < 0.45:
        return False

    mojibake_chars = sum(normalized.count(marker) for marker in ("Ã", "Â", "â", "�"))
    if visible_chars and mojibake_chars / visible_chars > 0.08:
        return False

    return True


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
