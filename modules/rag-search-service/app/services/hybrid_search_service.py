from app.search.score_normalizer import normalize_scores


class HybridSearchService:
    def merge(self, vector_results: list[dict], keyword_results: list[dict], vector_weight: float, keyword_weight: float) -> list[dict]:
        by_chunk_id: dict[str, dict] = {}

        for item in normalize_scores(vector_results, "vector_score", "vector_score_normalized"):
            merged = by_chunk_id.setdefault(item["chunk_id"], dict(item))
            merged["vector_score"] = item.get("vector_score")
            merged["vector_score_normalized"] = item.get("vector_score_normalized", 0.0)

        for item in normalize_scores(keyword_results, "keyword_score", "keyword_score_normalized"):
            merged = by_chunk_id.setdefault(item["chunk_id"], dict(item))
            merged["keyword_score"] = item.get("keyword_score")
            merged["keyword_score_normalized"] = item.get("keyword_score_normalized", 0.0)
            merged["exact_phrase_match"] = bool(merged.get("exact_phrase_match") or item.get("exact_phrase_match"))
            merged["resource_match_score"] = max(
                float(merged.get("resource_match_score") or 0.0),
                float(item.get("resource_match_score") or 0.0),
            )
            if not merged.get("vector_score"):
                merged.update({key: value for key, value in item.items() if key not in merged or merged[key] is None})

        for item in by_chunk_id.values():
            item["score"] = (
                float(item.get("vector_score_normalized") or 0.0) * vector_weight
                + float(item.get("keyword_score_normalized") or 0.0) * keyword_weight
            )
            if item.get("exact_phrase_match"):
                item["score"] = max(item["score"], 1.0)
            resource_match_score = float(item.get("resource_match_score") or 0.0)
            if resource_match_score:
                item["score"] += min(resource_match_score * 0.10, 0.20)
        return list(by_chunk_id.values())
