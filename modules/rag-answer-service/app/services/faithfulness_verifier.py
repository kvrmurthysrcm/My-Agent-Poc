import re
from dataclasses import dataclass, field
from typing import Any


CITATION_RE = re.compile(r"\[\s*Source\s+rank\s+(\d+)(?:[^\]]*?chunk\s+(\d+))?[^\]]*\]", flags=re.IGNORECASE)
TOKEN_RE = re.compile(r"[a-z][a-z']{2,}", flags=re.IGNORECASE)
STOPWORDS = {
    "and",
    "answer",
    "are",
    "but",
    "chunk",
    "context",
    "from",
    "has",
    "have",
    "his",
    "into",
    "not",
    "page",
    "rank",
    "she",
    "source",
    "that",
    "the",
    "their",
    "this",
    "was",
    "were",
    "with",
}


@dataclass(frozen=True)
class FaithfulnessResult:
    supported: bool
    cited_source_ranks: list[int] = field(default_factory=list)
    missing_citations: bool = False
    unknown_source_ranks: list[int] = field(default_factory=list)
    chunk_mismatches: list[dict[str, int]] = field(default_factory=list)
    evidence_overlap: float = 0.0
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "supported": self.supported,
            "cited_source_ranks": self.cited_source_ranks,
            "missing_citations": self.missing_citations,
            "unknown_source_ranks": self.unknown_source_ranks,
            "chunk_mismatches": self.chunk_mismatches,
            "evidence_overlap": round(self.evidence_overlap, 4),
            "reason": self.reason,
        }


class FaithfulnessVerifier:
    def verify(self, answer: str, selected_sources: list[dict[str, Any]]) -> FaithfulnessResult:
        normalized_answer = answer.strip()
        if not normalized_answer:
            return FaithfulnessResult(supported=False, missing_citations=True, reason="empty_answer")
        if normalized_answer.lower().startswith("insufficient_context"):
            return FaithfulnessResult(supported=True, reason="model_reported_insufficient_context")

        citations = self._extract_citations(normalized_answer)
        if not citations:
            return FaithfulnessResult(supported=False, missing_citations=True, reason="answer_has_no_source_rank_citations")

        source_by_rank = {int(item.get("rank") or 0): item for item in selected_sources}
        cited_ranks = sorted({rank for rank, _chunk in citations})
        unknown_ranks = [rank for rank in cited_ranks if rank not in source_by_rank]
        chunk_mismatches = self._chunk_mismatches(citations, source_by_rank)
        overlap = self._evidence_overlap(normalized_answer, selected_sources)

        if unknown_ranks:
            return FaithfulnessResult(
                supported=False,
                cited_source_ranks=cited_ranks,
                unknown_source_ranks=unknown_ranks,
                chunk_mismatches=chunk_mismatches,
                evidence_overlap=overlap,
                reason="answer_cites_source_ranks_not_in_context",
            )
        if chunk_mismatches:
            return FaithfulnessResult(
                supported=False,
                cited_source_ranks=cited_ranks,
                chunk_mismatches=chunk_mismatches,
                evidence_overlap=overlap,
                reason="answer_cites_wrong_chunk_for_source_rank",
            )
        if overlap < 0.20:
            return FaithfulnessResult(
                supported=False,
                cited_source_ranks=cited_ranks,
                evidence_overlap=overlap,
                reason="answer_terms_not_supported_by_selected_context",
            )

        return FaithfulnessResult(
            supported=True,
            cited_source_ranks=cited_ranks,
            evidence_overlap=overlap,
            reason="answer_citations_match_selected_context",
        )

    def _extract_citations(self, answer: str) -> list[tuple[int, int | None]]:
        citations: list[tuple[int, int | None]] = []
        for match in CITATION_RE.finditer(answer):
            rank = int(match.group(1))
            chunk = int(match.group(2)) if match.group(2) is not None else None
            citations.append((rank, chunk))
        return citations

    def _chunk_mismatches(
        self,
        citations: list[tuple[int, int | None]],
        source_by_rank: dict[int, dict[str, Any]],
    ) -> list[dict[str, int]]:
        mismatches: list[dict[str, int]] = []
        for rank, cited_chunk in citations:
            if cited_chunk is None or rank not in source_by_rank:
                continue
            actual_chunk = int(source_by_rank[rank].get("chunk_index") or 0)
            if cited_chunk != actual_chunk:
                mismatches.append({"source_rank": rank, "cited_chunk": cited_chunk, "actual_chunk": actual_chunk})
        return mismatches

    def _evidence_overlap(self, answer: str, selected_sources: list[dict[str, Any]]) -> float:
        answer_text = CITATION_RE.sub(" ", answer)
        answer_terms = self._terms(answer_text)
        if not answer_terms:
            return 0.0
        context_text = " ".join(str(item.get("chunk_text") or item.get("snippet") or "") for item in selected_sources)
        context_terms = self._terms(context_text)
        if not context_terms:
            return 0.0
        return len(answer_terms & context_terms) / len(answer_terms)

    def _terms(self, text: str) -> set[str]:
        return {
            token.lower().strip("'")[:10]
            for token in TOKEN_RE.findall(text)
            if token.lower().strip("'") not in STOPWORDS
        }
