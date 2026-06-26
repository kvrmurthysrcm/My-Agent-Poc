import re

from app.db.models import RagDocumentChunk, Resource


CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
PAGE_MARKER_RE = re.compile(r"\[Page\s+\d+\]", flags=re.IGNORECASE)
WHITESPACE_RE = re.compile(r"\s+")


class EmbeddingInputService:
    """Builds retrieval-oriented embedding text without changing stored chunk text."""

    def build(self, resource: Resource, chunk: RagDocumentChunk) -> str:
        context_parts = self._resource_context(resource)
        if chunk.section_title:
            context_parts.append(f"Section: {chunk.section_title}")
        if chunk.heading_path:
            context_parts.append("Heading path: " + " > ".join(str(item) for item in chunk.heading_path if item))
        if chunk.page_start:
            page_range = f"{chunk.page_start}-{chunk.page_end}" if chunk.page_end and chunk.page_end != chunk.page_start else str(chunk.page_start)
            context_parts.append(f"Page: {page_range}")

        chunk_text = self._clean_chunk_text(chunk.chunk_text, resource.title)
        context = "\n".join(context_parts)
        return f"{context}\n\n{chunk_text}".strip() if context else chunk_text

    def _resource_context(self, resource: Resource) -> list[str]:
        metadata = resource.resource_metadata or {}
        context = [f"Title: {resource.title}"]

        author = metadata.get("author")
        if author:
            context.append(f"Author: {author}")

        category = metadata.get("category_name")
        if category:
            context.append(f"Category: {category}")

        tags = metadata.get("tags")
        if tags:
            context.append("Tags: " + ", ".join(str(tag) for tag in tags if tag))

        description = metadata.get("description")
        if description:
            context.append(f"Description: {description}")

        return context

    def _clean_chunk_text(self, text: str, title: str | None) -> str:
        cleaned = CONTROL_CHARS_RE.sub(" ", text)
        cleaned = PAGE_MARKER_RE.sub(" ", cleaned)
        if title:
            escaped_title = re.escape(title.strip())
            if escaped_title:
                cleaned = re.sub(rf"\b{escaped_title}\b\s*\d*", " ", cleaned, flags=re.IGNORECASE)
        return WHITESPACE_RE.sub(" ", cleaned).strip()
