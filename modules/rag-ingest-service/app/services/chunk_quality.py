import re

from app.services.chunking_types import TextChunk
from app.services.page_markers import page_range_for_text
from app.utils.hashing import sha256_text
from app.utils.token_counter import count_tokens


PAGE_MARKER_RE = re.compile(r"\[Page\s+\d+\]", flags=re.IGNORECASE)
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")
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
FRONT_MATTER_PHRASES = (
    "all rights reserved",
    "copyright",
    "dedication",
    "edition",
    "impression",
    "isbn",
    "preface",
    "printed at",
    "publisher",
    "table of contents",
)


def clean_chunk_text(text: str) -> str:
    without_page_markers = PAGE_MARKER_RE.sub(" ", text)
    normalized_lines = [re.sub(r"\s+", " ", line).strip() for line in without_page_markers.splitlines()]
    return "\n".join(line for line in normalized_lines if line).strip()


def filter_quality_chunks(
    chunks: list[TextChunk],
    keep_numeric_table_chunks: bool = True,
    min_alpha_ratio: float = 0.45,
) -> list[TextChunk]:
    filtered: list[TextChunk] = []
    seen_hashes: set[str] = set()

    for chunk in chunks:
        cleaned_text = clean_chunk_text(chunk.chunk_text)
        classification = classify_chunk_text(
            cleaned_text,
            chunk_index=chunk.chunk_index,
            keep_numeric_table_chunks=keep_numeric_table_chunks,
            min_alpha_ratio=min_alpha_ratio,
        )
        if not classification["store"]:
            continue
        chunk_hash = sha256_text(cleaned_text)
        if chunk_hash in seen_hashes:
            continue
        seen_hashes.add(chunk_hash)
        page_start, page_end = page_range_for_text(chunk.chunk_text)
        filtered.append(
            TextChunk(
                chunk_index=len(filtered),
                chunk_text=cleaned_text,
                token_count=count_tokens(cleaned_text),
                char_count=len(cleaned_text),
                chunk_hash_sha256=chunk_hash,
                page_start=page_start or chunk.page_start,
                page_end=page_end or chunk.page_end,
                section_title=chunk.section_title,
                heading_path=chunk.heading_path,
                chunk_type=chunk.chunk_type,
                metadata={
                    **chunk.metadata,
                    "quality": classification["quality"],
                    "searchable": classification["searchable"],
                    "front_matter": classification["front_matter"],
                    "boilerplate": classification["boilerplate"],
                    "numeric_table_heavy": classification["numeric_table_heavy"],
                },
            )
        )

    return filtered


def is_searchable_chunk(text: str) -> bool:
    return bool(classify_chunk_text(text)["store"])


def classify_chunk_text(
    text: str,
    chunk_index: int = 0,
    keep_numeric_table_chunks: bool = True,
    min_alpha_ratio: float = 0.45,
) -> dict[str, bool | str]:
    normalized = re.sub(r"\s+", " ", text).strip()
    result: dict[str, bool | str] = {
        "store": False,
        "searchable": False,
        "quality": "filtered",
        "front_matter": False,
        "boilerplate": False,
        "numeric_table_heavy": False,
    }
    if not normalized:
        return result

    tokens = [token for token in TOKEN_RE.findall(normalized) if not ROMAN_RE.fullmatch(token)]
    meaningful_tokens = [token for token in tokens if len(token.strip("'-")) >= 3]
    lower = normalized.lower()
    boilerplate = any(phrase in lower for phrase in BOILERPLATE_PHRASES)
    front_matter = chunk_index <= 5 and any(phrase in lower for phrase in FRONT_MATTER_PHRASES)
    numeric_table_heavy = _is_numeric_table_heavy(normalized)

    result["front_matter"] = front_matter
    result["boilerplate"] = boilerplate
    result["numeric_table_heavy"] = numeric_table_heavy

    if len(meaningful_tokens) < 5:
        return result
    if boilerplate and len(meaningful_tokens) < 40:
        return result

    alpha_chars = sum(1 for char in normalized if char.isalpha())
    visible_chars = sum(1 for char in normalized if not char.isspace())
    if visible_chars and alpha_chars / visible_chars < min_alpha_ratio and not (
        keep_numeric_table_chunks and numeric_table_heavy
    ):
        return result

    mojibake_chars = sum(normalized.count(marker) for marker in ("Ãƒ", "Ã‚", "Ã¢Â€", "ï¿½"))
    if visible_chars and mojibake_chars / visible_chars > 0.08:
        return result

    result["store"] = True
    result["searchable"] = True
    result["quality"] = "front_matter" if front_matter else "searchable"
    return result


def _is_numeric_table_heavy(text: str) -> bool:
    visible_chars = [char for char in text if not char.isspace()]
    if not visible_chars:
        return False
    digit_chars = sum(1 for char in visible_chars if char.isdigit())
    table_separators = sum(text.count(marker) for marker in ("|", "\t", "  ", ",", ";", ":"))
    code_like_tokens = len(re.findall(r"\b[A-Z]{1,6}[-_/]?\d{2,}\b|\b\d+[A-Z]+[-_/]?\d*\b", text))
    return digit_chars / len(visible_chars) >= 0.25 and (table_separators >= 3 or code_like_tokens >= 2)
