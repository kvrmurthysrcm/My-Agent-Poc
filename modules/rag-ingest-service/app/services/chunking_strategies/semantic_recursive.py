import re

from app.services.chunking_strategies.base import ChunkingStrategy
from app.services.chunking_strategies.intelligent_recursive import split_sections
from app.services.chunking_types import TextChunk
from app.services.page_markers import page_range_for_text
from app.utils.hashing import sha256_text
from app.utils.token_counter import count_tokens

CHAPTER_HEADING_RE = re.compile(r"^(?P<number>\d{1,3}):\s+(?P<title>[A-Za-z][^\n]{2,120})$")
TRAILING_CHAPTER_HEADING_RE = re.compile(
    r"(?P<body>.+?)\s+(?P<heading>(?P<number>\d{1,3}):\s+(?P<title>[A-Z][^.!?\n]{2,80}))$",
    flags=re.DOTALL,
)
VERSE_MARKER_RE = re.compile(r"^(?P<chapter>\d{1,3})\.(?P<verse>\d{1,3})$")
VERSE_RANGE_RE = re.compile(r"\b(?P<chapter>\d{1,3})\.(?P<verse>\d{1,3})\b")
SPEAKERS = {"ashtavakra said": "Ashtavakra", "janaka said": "Janaka"}


class SemanticRecursiveChunkingStrategy(ChunkingStrategy):
    strategy_name = "SEMANTIC_RECURSIVE"

    def chunk(self, text: str, chunk_size_tokens: int, chunk_overlap_tokens: int) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        seen_hashes: set[str] = set()

        for section_title, section_text in split_sections(text):
            paragraphs = self._split_paragraphs(section_text)
            current: list[str] = []
            current_tokens = 0
            active_section_title = section_title
            active_metadata = self._metadata_for_section(active_section_title)

            for paragraph in paragraphs:
                chapter_heading = _parse_chapter_heading(paragraph)
                if chapter_heading:
                    chunks = self._flush_chunk(
                        chunks,
                        seen_hashes,
                        current,
                        active_section_title,
                        "paragraph_group",
                        active_metadata,
                    )
                    current = []
                    current_tokens = 0
                    active_section_title = chapter_heading["chapter_title"]
                    active_metadata = chapter_heading
                    continue

                paragraph, trailing_heading = self._detach_trailing_chapter_heading(paragraph)
                if not paragraph:
                    if trailing_heading:
                        active_section_title = trailing_heading["chapter_title"]
                        active_metadata = trailing_heading
                    continue
                paragraph_tokens = count_tokens(paragraph)
                if paragraph_tokens > chunk_size_tokens:
                    chunks = self._flush_chunk(
                        chunks,
                        seen_hashes,
                        current,
                        active_section_title,
                        "paragraph_group",
                        active_metadata,
                    )
                    current = []
                    current_tokens = 0
                    chunks.extend(
                        self._token_windows(
                            paragraph,
                            chunk_size_tokens,
                            chunk_overlap_tokens,
                            active_section_title,
                            len(chunks),
                            seen_hashes,
                            active_metadata,
                        )
                    )
                    if trailing_heading:
                        active_section_title = trailing_heading["chapter_title"]
                        active_metadata = trailing_heading
                    continue

                if current and current_tokens + paragraph_tokens > chunk_size_tokens:
                    chunks = self._flush_chunk(
                        chunks,
                        seen_hashes,
                        current,
                        active_section_title,
                        "paragraph_group",
                        active_metadata,
                    )
                    current = self._overlap_tail(current, chunk_overlap_tokens)
                    current_tokens = count_tokens("\n\n".join(current))

                current.append(paragraph)
                current_tokens += paragraph_tokens
                if trailing_heading:
                    chunks = self._flush_chunk(
                        chunks,
                        seen_hashes,
                        current,
                        active_section_title,
                        "paragraph_group",
                        active_metadata,
                    )
                    current = []
                    current_tokens = 0
                    active_section_title = trailing_heading["chapter_title"]
                    active_metadata = trailing_heading

            chunks = self._flush_chunk(
                chunks,
                seen_hashes,
                current,
                active_section_title,
                "paragraph_group",
                active_metadata,
            )

        return [self._with_index(chunk, index) for index, chunk in enumerate(chunks)]

    def _split_paragraphs(self, text: str) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
        if len(paragraphs) > 1:
            return self._merge_orphan_verse_markers(paragraphs)
        return self._merge_orphan_verse_markers([line.strip() for line in text.splitlines() if line.strip()])

    def _merge_orphan_verse_markers(self, units: list[str]) -> list[str]:
        merged: list[str] = []
        pending_marker: str | None = None
        for unit in units:
            if VERSE_MARKER_RE.fullmatch(unit.strip()):
                if pending_marker:
                    merged.append(pending_marker)
                pending_marker = unit.strip()
                continue
            if pending_marker:
                merged.append(f"{pending_marker}\n{unit}")
                pending_marker = None
            else:
                merged.append(unit)
        if pending_marker:
            if merged:
                merged[-1] = f"{merged[-1]}\n{pending_marker}"
            else:
                merged.append(pending_marker)
        return merged

    def _flush_chunk(
        self,
        chunks: list[TextChunk],
        seen_hashes: set[str],
        paragraphs: list[str],
        section_title: str | None,
        chunk_type: str,
        base_metadata: dict[str, str | int] | None = None,
    ) -> list[TextChunk]:
        chunk_text = "\n\n".join(paragraphs).strip()
        if not chunk_text:
            return chunks
        chunk_hash = sha256_text(chunk_text)
        if chunk_hash in seen_hashes:
            return chunks
        seen_hashes.add(chunk_hash)
        page_start, page_end = page_range_for_text(chunk_text)
        metadata = {
            "strategy": self.strategy_name,
            "split_basis": chunk_type,
            **(base_metadata or self._metadata_for_section(section_title)),
            **self._metadata_for_chunk(chunk_text),
        }
        chunks.append(
            TextChunk(
                chunk_index=len(chunks),
                chunk_text=chunk_text,
                token_count=count_tokens(chunk_text),
                char_count=len(chunk_text),
                chunk_hash_sha256=chunk_hash,
                page_start=page_start,
                page_end=page_end,
                section_title=section_title,
                heading_path=[section_title] if section_title else [],
                chunk_type=chunk_type,
                metadata=metadata,
            )
        )
        return chunks

    def _token_windows(
        self,
        text: str,
        chunk_size_tokens: int,
        chunk_overlap_tokens: int,
        section_title: str | None,
        first_index: int,
        seen_hashes: set[str],
        base_metadata: dict[str, str | int] | None = None,
    ) -> list[TextChunk]:
        words = text.split()
        chunks: list[TextChunk] = []
        step = max(1, chunk_size_tokens - chunk_overlap_tokens)
        start = 0
        while start < len(words):
            chunk_text = " ".join(words[start : start + chunk_size_tokens]).strip()
            chunk_hash = sha256_text(chunk_text)
            if chunk_text and chunk_hash not in seen_hashes:
                seen_hashes.add(chunk_hash)
                page_start, page_end = page_range_for_text(chunk_text)
                metadata = {
                    "strategy": self.strategy_name,
                    "split_basis": "fallback_token_window",
                    **(base_metadata or self._metadata_for_section(section_title)),
                    **self._metadata_for_chunk(chunk_text),
                }
                chunks.append(
                    TextChunk(
                        chunk_index=first_index + len(chunks),
                        chunk_text=chunk_text,
                        token_count=count_tokens(chunk_text),
                        char_count=len(chunk_text),
                        chunk_hash_sha256=chunk_hash,
                        page_start=page_start,
                        page_end=page_end,
                        section_title=section_title,
                        heading_path=[section_title] if section_title else [],
                        chunk_type="fallback_token_window",
                        metadata=metadata,
                    )
                )
            if start + chunk_size_tokens >= len(words):
                break
            start += step
        return chunks

    def _overlap_tail(self, paragraphs: list[str], overlap_tokens: int) -> list[str]:
        if overlap_tokens <= 0 or not paragraphs:
            return []
        tail_words = " ".join(paragraphs).split()[-overlap_tokens:]
        if not tail_words:
            return []
        return [" ".join(tail_words)]

    def _with_index(self, chunk: TextChunk, index: int) -> TextChunk:
        return TextChunk(
            chunk_index=index,
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

    def _metadata_for_section(self, section_title: str | None) -> dict[str, str]:
        if not section_title:
            return {}
        speaker = SPEAKERS.get(section_title.strip().lower())
        if speaker:
            return {"speaker": speaker}
        chapter_heading = _parse_chapter_heading(section_title)
        if chapter_heading:
            return chapter_heading
        return {}

    def _metadata_for_chunk(self, chunk_text: str) -> dict[str, str | int]:
        verse_matches = list(VERSE_RANGE_RE.finditer(chunk_text))
        if not verse_matches:
            return {}
        first = verse_matches[0]
        last = verse_matches[-1]
        return {
            "verse_start": first.group(0),
            "verse_end": last.group(0),
            "chapter_number": int(first.group("chapter")),
        }

    def _detach_trailing_chapter_heading(self, paragraph: str) -> tuple[str, dict[str, str | int] | None]:
        match = TRAILING_CHAPTER_HEADING_RE.match(paragraph.strip())
        if not match:
            return paragraph, None
        return match.group("body").strip(), {
            "chapter_number": int(match.group("number")),
            "chapter_title": match.group("title").strip(),
        }


def _parse_chapter_heading(text: str) -> dict[str, str | int] | None:
    match = CHAPTER_HEADING_RE.fullmatch(text.strip())
    if not match:
        return None
    return {
        "chapter_number": int(match.group("number")),
        "chapter_title": match.group("title").strip(),
    }
