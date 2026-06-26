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
    "download free ebooks",
    "free ebooks at",
    "planet ebook",
    "publications division",
    "printed at",
    "tirumala tirupati devasthanams press",
)


def clean_chunk_text(text: str) -> str:
    without_page_markers = PAGE_MARKER_RE.sub(" ", text)
    normalized_lines = [re.sub(r"\s+", " ", line).strip() for line in without_page_markers.splitlines()]
    return "\n".join(line for line in normalized_lines if line).strip()


def filter_quality_chunks(chunks: list[TextChunk]) -> list[TextChunk]:
    filtered: list[TextChunk] = []
    seen_hashes: set[str] = set()

    for chunk in chunks:
        cleaned_text = clean_chunk_text(chunk.chunk_text)
        if not is_searchable_chunk(cleaned_text):
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
                metadata={**chunk.metadata, "quality": "searchable"},
            )
        )

    return filtered


def is_searchable_chunk(text: str) -> bool:
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return False

    tokens = [token for token in TOKEN_RE.findall(normalized) if not ROMAN_RE.fullmatch(token)]
    meaningful_tokens = [token for token in tokens if len(token.strip("'-")) >= 3]
    lower = normalized.lower()

    if len(meaningful_tokens) < 5:
        return False
    if any(phrase in lower for phrase in BOILERPLATE_PHRASES) and len(meaningful_tokens) < 40:
        return False

    alpha_chars = sum(1 for char in normalized if char.isalpha())
    visible_chars = sum(1 for char in normalized if not char.isspace())
    if visible_chars and alpha_chars / visible_chars < 0.45:
        return False

    mojibake_chars = sum(normalized.count(marker) for marker in ("Ã", "Â", "â", "�"))
    if visible_chars and mojibake_chars / visible_chars > 0.08:
        return False

    return True
