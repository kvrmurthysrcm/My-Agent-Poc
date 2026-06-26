class RankingService:
    def rank(self, items: list[dict], min_score: float, limit: int) -> list[dict]:
        ranked = [item for item in items if float(item.get("score") or 0.0) >= min_score]
        ranked.sort(
            key=lambda item: (
                -int(bool(item.get("exact_phrase_match"))),
                -float(item.get("resource_match_score") or 0.0),
                int(item.get("chunk_index") or 0) if float(item.get("resource_match_score") or 0.0) else 0,
                -float(item.get("score") or 0.0),
            )
        )
        return ranked[:limit]
