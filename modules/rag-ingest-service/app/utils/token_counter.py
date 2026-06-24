import re


TOKEN_PATTERN = re.compile(r"\w+|[^\w\s]", re.UNICODE)


def count_tokens(text: str) -> int:
    return len(TOKEN_PATTERN.findall(text))


def tokenize(text: str) -> list[str]:
    return TOKEN_PATTERN.findall(text)
