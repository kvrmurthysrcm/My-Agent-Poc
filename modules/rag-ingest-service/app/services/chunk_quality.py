import json
import re
from functools import lru_cache
from pathlib import Path

from app.core.config import get_settings
from app.services.chunking_types import TextChunk
from app.services.page_markers import page_range_for_text
from app.utils.hashing import sha256_text
from app.utils.token_counter import count_tokens


PAGE_MARKER_RE = re.compile(r"\[Page\s+\d+\]", flags=re.IGNORECASE)
TOKEN_RE = re.compile(r"[A-Za-z0-9][A-Za-z0-9'-]*")
ROMAN_RE = re.compile(r"^[ivxlcdm]+$", flags=re.IGNORECASE)
DEFAULT_RULES = {
    "boilerplate_phrases": (
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
    ),
    "front_matter_phrases": (
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
    ),
    "toc_phrases": ("chapter 1:", "chapter 2:", "chapter 3:", "contents", "table of contents"),
}


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
        content_type = str(classification["quality"])
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
                    "content_type": content_type,
                    "searchable": classification["searchable"],
                    "front_matter": classification["front_matter"],
                    "toc": classification["toc"],
                    "boilerplate": classification["boilerplate"],
                    "numeric_table_heavy": classification["numeric_table_heavy"],
                },
            )
        )

    return _merge_small_chunks(filtered, get_settings().minimum_chunk_tokens)


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
        "toc": False,
        "boilerplate": False,
        "numeric_table_heavy": False,
    }
    if not normalized:
        return result

    tokens = [token for token in TOKEN_RE.findall(normalized) if not ROMAN_RE.fullmatch(token)]
    meaningful_tokens = [token for token in tokens if len(token.strip("'-")) >= 3]
    lower = normalized.lower()
    rules = load_chunk_quality_rules()
    boilerplate = any(phrase in lower for phrase in rules["boilerplate_phrases"])
    front_matter = chunk_index <= 5 and any(phrase in lower for phrase in rules["front_matter_phrases"])
    toc = chunk_index <= 5 and sum(1 for phrase in rules["toc_phrases"] if phrase in lower) >= 2
    numeric_table_heavy = _is_numeric_table_heavy(normalized)

    result["front_matter"] = front_matter
    result["toc"] = toc
    result["boilerplate"] = boilerplate
    result["numeric_table_heavy"] = numeric_table_heavy

    if len(meaningful_tokens) < 5:
        return result
    if boilerplate and len(meaningful_tokens) < 40 and not front_matter:
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
    result["searchable"] = not (front_matter or toc)
    if toc:
        result["quality"] = "toc"
    elif front_matter:
        result["quality"] = "front_matter"
    else:
        result["quality"] = "searchable"
    return result


@lru_cache
def load_chunk_quality_rules() -> dict[str, tuple[str, ...]]:
    rules_path = get_settings().chunk_quality_rules_path
    candidates = [rules_path]
    if not rules_path.is_absolute():
        candidates.append(Path(__file__).resolve().parents[1] / "config" / rules_path.name)

    data: dict[str, list[str]] = {}
    for candidate in candidates:
        if candidate.exists():
            data = json.loads(candidate.read_text(encoding="utf-8"))
            break

    return {
        key: tuple(_normalize_phrases(data.get(key, DEFAULT_RULES[key])))
        for key in ("boilerplate_phrases", "front_matter_phrases", "toc_phrases")
    }


def _normalize_phrases(values: list[str] | tuple[str, ...]) -> list[str]:
    return [re.sub(r"\s+", " ", value).strip().lower() for value in values if value.strip()]


def _merge_small_chunks(chunks: list[TextChunk], minimum_tokens: int) -> list[TextChunk]:
    effective_minimum_tokens = min(minimum_tokens, 25)
    if effective_minimum_tokens <= 0 or len(chunks) <= 1:
        return chunks

    merged: list[TextChunk] = []
    index = 0
    while index < len(chunks):
        current = chunks[index]
        if current.token_count >= effective_minimum_tokens:
            merged.append(current)
            index += 1
            continue

        if index + 1 < len(chunks) and _can_merge_chunks(current, chunks[index + 1]):
            merged.append(_combine_chunks(current, chunks[index + 1], len(merged)))
            index += 2
        elif merged and _can_merge_chunks(merged[-1], current):
            merged[-1] = _combine_chunks(merged[-1], current, len(merged) - 1)
            index += 1
        else:
            merged.append(current)
            index += 1

    return [_reindex_chunk(chunk, chunk_index) for chunk_index, chunk in enumerate(merged)]


def _can_merge_chunks(first: TextChunk, second: TextChunk) -> bool:
    first_chapter = first.metadata.get("chapter_number")
    second_chapter = second.metadata.get("chapter_number")
    if first_chapter and second_chapter and first_chapter != second_chapter:
        return False
    return True


def _combine_chunks(first: TextChunk, second: TextChunk, chunk_index: int) -> TextChunk:
    chunk_text = f"{first.chunk_text}\n\n{second.chunk_text}".strip()
    chunk_hash = sha256_text(chunk_text)
    page_values = [value for value in (first.page_start, first.page_end, second.page_start, second.page_end) if value]
    metadata = {
        **first.metadata,
        **second.metadata,
        "merged_small_chunk": True,
        "merged_chunk_indices": [first.chunk_index, second.chunk_index],
    }
    return TextChunk(
        chunk_index=chunk_index,
        chunk_text=chunk_text,
        token_count=count_tokens(chunk_text),
        char_count=len(chunk_text),
        chunk_hash_sha256=chunk_hash,
        page_start=min(page_values) if page_values else None,
        page_end=max(page_values) if page_values else None,
        section_title=first.section_title or second.section_title,
        heading_path=first.heading_path or second.heading_path,
        chunk_type=first.chunk_type if first.chunk_type == second.chunk_type else "merged_small_chunk",
        metadata=metadata,
    )


def _reindex_chunk(chunk: TextChunk, chunk_index: int) -> TextChunk:
    if chunk.chunk_index == chunk_index:
        return chunk
    return TextChunk(
        chunk_index=chunk_index,
        chunk_text=chunk.chunk_text,
        token_count=chunk.token_count,
        char_count=chunk.char_count,
        chunk_hash_sha256=chunk.chunk_hash_sha256,
        page_start=chunk.page_start,
        page_end=chunk.page_end,
        section_title=chunk.section_title,
        heading_path=chunk.heading_path,
        chunk_type=chunk.chunk_type,
        metadata=chunk.metadata,
    )


def _is_numeric_table_heavy(text: str) -> bool:
    visible_chars = [char for char in text if not char.isspace()]
    if not visible_chars:
        return False
    digit_chars = sum(1 for char in visible_chars if char.isdigit())
    table_separators = sum(text.count(marker) for marker in ("|", "\t", "  ", ",", ";", ":"))
    code_like_tokens = len(re.findall(r"\b[A-Z]{1,6}[-_/]?\d{2,}\b|\b\d+[A-Z]+[-_/]?\d*\b", text))
    return digit_chars / len(visible_chars) >= 0.25 and (table_separators >= 3 or code_like_tokens >= 2)
