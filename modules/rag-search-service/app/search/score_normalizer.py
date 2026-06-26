from collections.abc import Iterable


def normalize_scores(items: Iterable[dict], score_key: str, output_key: str) -> list[dict]:
    normalized_items = [dict(item) for item in items]
    if not normalized_items:
        return []

    values = [float(item.get(score_key) or 0.0) for item in normalized_items]
    min_value = min(values)
    max_value = max(values)
    span = max_value - min_value

    for item, value in zip(normalized_items, values, strict=False):
        item[output_key] = 1.0 if span == 0 and value > 0 else ((value - min_value) / span if span else 0.0)
    return normalized_items
