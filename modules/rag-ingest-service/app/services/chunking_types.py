from dataclasses import dataclass, field


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
