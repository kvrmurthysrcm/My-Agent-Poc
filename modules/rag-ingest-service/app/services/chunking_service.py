from dataclasses import dataclass, field

from app.utils.hashing import sha256_text
from app.utils.token_counter import count_tokens


@dataclass(frozen=True)
class TextChunk:
    chunk_index: int
    chunk_text: str
    token_count: int
    char_count: int
    chunk_hash_sha256: str
    page_start: int | None = None
    page_end: int | None = None
    section_title: str | None = None
    heading_path: list[str] = field(default_factory=list)
    chunk_type: str = "text"
    metadata: dict = field(default_factory=dict)


class ChunkingService:
    def chunk(self, text: str, chunk_size_tokens: int, chunk_overlap_tokens: int) -> list[TextChunk]:
        sections = self._split_sections(text)
        chunks: list[TextChunk] = []
        seen_hashes: set[str] = set()
        index = 0

        for section_title, section_text in sections:
            words = section_text.split()
            if not words:
                continue
            step = max(1, chunk_size_tokens - chunk_overlap_tokens)
            start = 0
            while start < len(words):
                window = words[start : start + chunk_size_tokens]
                chunk_text = " ".join(window).strip()
                chunk_hash = sha256_text(chunk_text)
                if chunk_text and chunk_hash not in seen_hashes:
                    seen_hashes.add(chunk_hash)
                    chunks.append(
                        TextChunk(
                            chunk_index=index,
                            chunk_text=chunk_text,
                            token_count=count_tokens(chunk_text),
                            char_count=len(chunk_text),
                            chunk_hash_sha256=chunk_hash,
                            section_title=section_title,
                            heading_path=[section_title] if section_title else [],
                            metadata={"strategy": "INTELLIGENT_RECURSIVE"},
                        )
                    )
                    index += 1
                if start + chunk_size_tokens >= len(words):
                    break
                start += step
        return chunks

    def _split_sections(self, text: str) -> list[tuple[str | None, str]]:
        sections: list[tuple[str | None, list[str]]] = [(None, [])]
        current_title: str | None = None

        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            is_heading = len(line) <= 120 and (line.isupper() or line.startswith("#") or line.endswith(":"))
            if is_heading:
                current_title = line.strip("#: ")
                sections.append((current_title, []))
            else:
                sections[-1][1].append(line)

        return [(title, "\n".join(lines)) for title, lines in sections if lines]
