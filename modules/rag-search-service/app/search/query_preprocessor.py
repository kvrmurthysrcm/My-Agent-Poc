import re
from dataclasses import dataclass
from typing import Literal

from app.search.lexical import DEFAULT_TOKEN_ALIASES, tokenize_meaningful


QUESTION_PREFIX_RE = re.compile(
    r"^(please\s+)?(can you\s+)?(tell me about|summarize|summary of|what is|who is|give me|show me|find|search for)\s+",
    flags=re.IGNORECASE,
)
SUBJECT_PREFIX_RE = re.compile(r"^(the\s+)?(novel|book|document|text)\s*:\s*", flags=re.IGNORECASE)
QUOTE_RE = re.compile(r"['\"]([^'\"]{8,})['\"]")
SUMMARY_RE = re.compile(r"\b(summary|summarize|overview|brief|tell me about|what is this about)\b", flags=re.IGNORECASE)
QUESTION_RE = re.compile(r"\b(who|what|when|where|why|how|which|did|does|do|is|are|was|were)\b", flags=re.IGNORECASE)

QueryIntent = Literal["exact_quote", "title_lookup", "summary_request", "factual_question", "broad_document_query"]


@dataclass(frozen=True)
class QueryUnderstanding:
    original_query: str
    normalized_query: str
    query_intent: QueryIntent
    normalized_terms: list[str]
    spelling_normalized: bool = False


class QueryPreprocessor:
    def __init__(self, aliases: dict[str, str] | None = None):
        self.aliases = aliases or dict(DEFAULT_TOKEN_ALIASES)

    def normalize(self, query: str) -> str:
        return self.understand(query).normalized_query

    def understand(self, query: str) -> QueryUnderstanding:
        normalized = re.sub(r"\s+", " ", query).strip()
        quoted = QUOTE_RE.search(normalized)
        if quoted:
            candidate = quoted.group(1).strip()
        else:
            candidate = normalized

        without_question = QUESTION_PREFIX_RE.sub("", candidate).strip()
        without_subject = SUBJECT_PREFIX_RE.sub("", without_question).strip()
        cleaned = without_subject or without_question or candidate
        spelling_normalized_query = self._normalize_spelling(cleaned)
        terms = tokenize_meaningful(spelling_normalized_query, aliases=self.aliases)
        return QueryUnderstanding(
            original_query=normalized,
            normalized_query=spelling_normalized_query or cleaned or normalized,
            query_intent=self._detect_intent(
                original=normalized,
                cleaned=spelling_normalized_query or cleaned,
                terms=terms,
                has_quote=bool(quoted),
            ),
            normalized_terms=terms,
            spelling_normalized=cleaned != spelling_normalized_query,
        )

    def _normalize_spelling(self, query: str) -> str:
        def replace(match: re.Match[str]) -> str:
            token = match.group(0)
            normalized = self.aliases.get(token.lower())
            if not normalized:
                return token
            if token.isupper():
                return normalized.upper()
            if token[0].isupper():
                return normalized.capitalize()
            return normalized

        return re.sub(r"[A-Za-z][A-Za-z'-]*", replace, query).strip()

    def _detect_intent(self, original: str, cleaned: str, terms: list[str], has_quote: bool) -> QueryIntent:
        if has_quote:
            return "exact_quote"
        if self._looks_like_exact_quote(cleaned):
            return "exact_quote"
        if SUMMARY_RE.search(original):
            return "summary_request"
        if QUESTION_RE.search(original) or original.endswith("?"):
            return "factual_question"
        if 0 < len(set(terms)) <= 4:
            return "title_lookup"
        return "broad_document_query"

    def _looks_like_exact_quote(self, query: str) -> bool:
        words = query.split()
        if len(words) < 8:
            return False
        punctuation_count = sum(query.count(mark) for mark in (",", ";", ":", ".", "!", "?"))
        return punctuation_count >= 2
