import re

from app.services.chunking_strategies.base import ChunkingStrategy
from app.services.chunking_strategies.intelligent_recursive import split_sections
from app.services.chunking_types import TextChunk
from app.utils.hashing import sha256_text
from app.utils.token_counter import count_tokens


class SemanticRecursiveChunkingStrategy(ChunkingStrategy):
    strategy_name = "SEMANTIC_RECURSIVE"

    def chunk(self, text: str, chunk_size_tokens: int, chunk_overlap_tokens: int) -> list[TextChunk]:
        chunks: list[TextChunk] = []
        seen_hashes: set[str] = set()

        for section_title, section_text in split_sections(text):
            paragraphs = self._split_paragraphs(section_text)
            current: list[str] = []
            current_tokens = 0

            for paragraph in paragraphs:
                paragraph_tokens = count_tokens(paragraph)
                if paragraph_tokens > chunk_size_tokens:
                    chunks = self._flush_chunk(chunks, seen_hashes, current, section_title, "paragraph_group")
                    current = []
                    current_tokens = 0
                    chunks.extend(
                        self._token_windows(
                            paragraph,
                            chunk_size_tokens,
                            chunk_overlap_tokens,
                            section_title,
                            len(chunks),
                            seen_hashes,
                        )
                    )
                    continue

                if current and current_tokens + paragraph_tokens > chunk_size_tokens:
                    chunks = self._flush_chunk(chunks, seen_hashes, current, section_title, "paragraph_group")
                    current = self._overlap_tail(current, chunk_overlap_tokens)
                    current_tokens = count_tokens("\n\n".join(current))

                current.append(paragraph)
                current_tokens += paragraph_tokens

            chunks = self._flush_chunk(chunks, seen_hashes, current, section_title, "paragraph_group")

        return [self._with_index(chunk, index) for index, chunk in enumerate(chunks)]

    def _split_paragraphs(self, text: str) -> list[str]:
        paragraphs = [part.strip() for part in re.split(r"\n\s*\n+", text) if part.strip()]
        if len(paragraphs) > 1:
            return paragraphs
        return [line.strip() for line in text.splitlines() if line.strip()]

    def _flush_chunk(
        self,
        chunks: list[TextChunk],
        seen_hashes: set[str],
        paragraphs: list[str],
        section_title: str | None,
        chunk_type: str,
    ) -> list[TextChunk]:
        chunk_text = "\n\n".join(paragraphs).strip()
        if not chunk_text:
            return chunks
        chunk_hash = sha256_text(chunk_text)
        if chunk_hash in seen_hashes:
            return chunks
        seen_hashes.add(chunk_hash)
        chunks.append(
            TextChunk(
                chunk_index=len(chunks),
                chunk_text=chunk_text,
                token_count=count_tokens(chunk_text),
                char_count=len(chunk_text),
                chunk_hash_sha256=chunk_hash,
                section_title=section_title,
                heading_path=[section_title] if section_title else [],
                chunk_type=chunk_type,
                metadata={"strategy": self.strategy_name, "split_basis": chunk_type},
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
                chunks.append(
                    TextChunk(
                        chunk_index=first_index + len(chunks),
                        chunk_text=chunk_text,
                        token_count=count_tokens(chunk_text),
                        char_count=len(chunk_text),
                        chunk_hash_sha256=chunk_hash,
                        section_title=section_title,
                        heading_path=[section_title] if section_title else [],
                        chunk_type="fallback_token_window",
                        metadata={"strategy": self.strategy_name, "split_basis": "fallback_token_window"},
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
