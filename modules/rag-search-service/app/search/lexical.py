import re
from collections import Counter
from json import loads
from pathlib import Path


STOPWORDS = {
    "a",
    "about",
    "all",
    "also",
    "am",
    "an",
    "and",
    "any",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "give",
    "has",
    "have",
    "how",
    "in",
    "into",
    "is",
    "it",
    "me",
    "much",
    "novel",
    "of",
    "on",
    "or",
    "search",
    "show",
    "tell",
    "that",
    "the",
    "their",
    "there",
    "these",
    "this",
    "to",
    "was",
    "what",
    "when",
    "where",
    "who",
    "with",
}

TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9'-]*", flags=re.IGNORECASE)
DEFAULT_TOKEN_ALIASES = loads((Path(__file__).with_name("default_query_aliases.json")).read_text(encoding="utf-8"))


def tokenize_meaningful(text: str, aliases: dict[str, str] | None = None) -> list[str]:
    return [
        normalize_token(token.lower().strip("'-"), aliases=aliases)
        for token in TOKEN_RE.findall(text)
        if len(token.strip("'-")) >= 3 and token.lower().strip("'-") not in STOPWORDS
    ]


def token_counts(text: str, aliases: dict[str, str] | None = None) -> Counter[str]:
    return Counter(tokenize_meaningful(text, aliases=aliases))


def normalized_text(text: str, aliases: dict[str, str] | None = None) -> str:
    return " ".join(normalize_token(token.lower().strip("'-"), aliases=aliases) for token in TOKEN_RE.findall(text))


def phrase_in_text(phrase: str, text: str, aliases: dict[str, str] | None = None) -> bool:
    normalized_phrase = normalized_text(phrase, aliases=aliases)
    if not normalized_phrase:
        return False
    return normalized_phrase in normalized_text(text, aliases=aliases)


def normalize_token(token: str, aliases: dict[str, str] | None = None) -> str:
    lookup = aliases if aliases is not None else DEFAULT_TOKEN_ALIASES
    return lookup.get(token, token)
