import re


QUESTION_PREFIX_RE = re.compile(
    r"^(tell me about|what is|who is|give me|show me|find|search for)\s+",
    flags=re.IGNORECASE,
)
SUBJECT_PREFIX_RE = re.compile(r"^(the\s+)?(novel|book|document|text)\s*:\s*", flags=re.IGNORECASE)


class QueryPreprocessor:
    def normalize(self, query: str) -> str:
        normalized = re.sub(r"\s+", " ", query).strip()
        without_question = QUESTION_PREFIX_RE.sub("", normalized).strip()
        without_subject = SUBJECT_PREFIX_RE.sub("", without_question).strip()
        return without_subject or without_question or normalized
