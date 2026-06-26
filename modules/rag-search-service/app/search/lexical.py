import re
from collections import Counter


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
TOKEN_ALIASES = {
    "bhagawat": "bhagavad",
    "bhagawad": "bhagavad",
    "geetha": "gita",
    "githa": "gita",
    "ramayana": "ramayan",
}


def tokenize_meaningful(text: str) -> list[str]:
    return [
        normalize_token(token.lower().strip("'-"))
        for token in TOKEN_RE.findall(text)
        if len(token.strip("'-")) >= 3 and token.lower().strip("'-") not in STOPWORDS
    ]


def token_counts(text: str) -> Counter[str]:
    return Counter(tokenize_meaningful(text))


def normalized_text(text: str) -> str:
    return " ".join(normalize_token(token.lower().strip("'-")) for token in TOKEN_RE.findall(text))


def phrase_in_text(phrase: str, text: str) -> bool:
    normalized_phrase = normalized_text(phrase)
    if not normalized_phrase:
        return False
    return normalized_phrase in normalized_text(text)


def normalize_token(token: str) -> str:
    return TOKEN_ALIASES.get(token, token)
