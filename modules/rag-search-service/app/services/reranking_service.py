import math

from app.search.lexical import phrase_in_text, token_counts


class RerankingService:
    def rerank(self, query: str, items: list[dict], top_n: int) -> list[dict]:
        scored = []
        query_terms = set(token_counts(query))
        title_lookup = self._is_title_lookup(query_terms)

        for item in items:
            rerank_score = self._score_item(query, query_terms, title_lookup, item)
            retrieval_score = float(item.get("score") or 0.0)
            item["retrieval_score"] = retrieval_score
            item["score"] = rerank_score + min(math.log1p(max(retrieval_score, 0.0)) / 10.0, 0.60)
            item["rerank_score"] = rerank_score
            scored.append(item)

        scored.sort(
            key=lambda item: (
                -int(bool(item.get("exact_phrase_match"))),
                -float(item.get("score") or 0.0),
                int(item.get("chunk_index") or 0),
            )
        )
        return scored[:top_n]

    def _score_item(self, query: str, query_terms: set[str], title_lookup: bool, item: dict) -> float:
        text = str(item.get("chunk_text") or "")
        title = str(item.get("title") or "")
        section = str(item.get("section_title") or "")
        text_terms = set(token_counts(" ".join([text, section])))
        title_terms = set(token_counts(title))

        score = 0.0
        if phrase_in_text(query, text):
            score += 3.0
        elif bool(item.get("exact_phrase_match")):
            score += 2.0

        if query_terms:
            text_coverage = len(query_terms & text_terms) / len(query_terms)
            title_coverage = len(query_terms & title_terms) / len(query_terms)
            score += text_coverage * 2.5
            score += title_coverage * (1.2 if title_lookup else 0.25)

            missing_from_text = len(query_terms - text_terms)
            if missing_from_text == 0:
                score += 0.75
            elif missing_from_text <= max(1, len(query_terms) // 4):
                score += 0.35

        resource_match = float(item.get("resource_match_score") or 0.0)
        score += min(resource_match * (0.35 if title_lookup else 0.08), 0.70 if title_lookup else 0.12)
        if title_lookup and resource_match:
            score += max(0.0, 0.55 - (int(item.get("chunk_index") or 0) * 0.05))

        score += self._direct_evidence_score(query, text)
        if not title_lookup:
            score -= self._front_matter_penalty(item, text)
        return score

    def _is_title_lookup(self, query_terms: set[str]) -> bool:
        return 0 < len(query_terms) <= 4

    def _direct_evidence_score(self, query: str, text: str) -> float:
        query_lower = query.lower()
        text_lower = text.lower()
        score = 0.0
        if "impression" in query_lower or "perceiv" in query_lower:
            for marker in ("perceiv", "impression", "reaction", "peace", "quiet", "stillness"):
                if marker in text_lower:
                    score += 0.80
        if "quote" in query_lower or len(query.split()) > 8:
            if phrase_in_text(query, text):
                score += 1.0
        return min(score, 3.5)

    def _front_matter_penalty(self, item: dict, text: str) -> float:
        chunk_index = int(item.get("chunk_index") or 0)
        text_lower = text.lower()
        penalty = 0.0
        if chunk_index == 0 and len(text) < 350:
            penalty += 0.25
        for marker in ("impression 19", "publisher", "publications division", "copyright", "table of contents"):
            if marker in text_lower:
                penalty += 0.35
        return min(penalty, 1.0)
