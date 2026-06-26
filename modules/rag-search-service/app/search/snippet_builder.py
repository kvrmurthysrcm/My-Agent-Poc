import re


class SnippetBuilder:
    def build(self, text: str, query: str, max_chars: int = 320) -> str:
        clean_text = re.sub(r"\s+", " ", text).strip()
        if len(clean_text) <= max_chars:
            return clean_text

        terms = [re.escape(term) for term in query.split() if len(term) > 2]
        match = re.search("|".join(terms), clean_text, flags=re.IGNORECASE) if terms else None
        if not match:
            return clean_text[: max_chars - 3].rstrip() + "..."

        start = max(match.start() - max_chars // 3, 0)
        end = min(start + max_chars, len(clean_text))
        snippet = clean_text[start:end].strip()
        if start > 0:
            snippet = "..." + snippet
        if end < len(clean_text):
            snippet += "..."
        return snippet
