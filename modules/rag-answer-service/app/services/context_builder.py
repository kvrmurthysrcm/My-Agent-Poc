import re
from typing import Any


class ContextBuilder:
    def build(
        self,
        search_response: dict[str, Any],
        context_top_k: int,
        max_chars: int,
        query: str = "",
        max_chars_per_source: int = 1800,
    ) -> tuple[str, list[dict[str, Any]]]:
        selected: list[dict[str, Any]] = []
        context_parts: list[str] = []
        remaining = max_chars

        query_weights = self._query_weights(query)
        results = sorted(
            (search_response.get("results") or [])[:context_top_k],
            key=lambda item: self._item_focus_score(item, query_weights),
            reverse=True,
        )
        reserved_per_source = max(500, (max_chars - (len(results) * 180)) // max(1, len(results)))

        for item in results:
            text = (item.get("chunk_text") or item.get("snippet") or "").strip()
            if not text:
                continue
            per_source_limit = min(max_chars_per_source, reserved_per_source, max(500, remaining - 250))
            text = self._excerpt(text, query=query, limit=per_source_limit)
            citation = self._citation_label(item)
            block = f"{citation}\n{text}"
            if len(block) > remaining:
                if remaining < 500:
                    break
                block = block[:remaining].rstrip()
            context_parts.append(block)
            selected.append(item)
            remaining -= len(block)
            if remaining <= 0:
                break

        return "\n\n".join(context_parts), selected

    def _excerpt(self, text: str, query: str, limit: int) -> str:
        compacted = re.sub(r"\s+", " ", text).strip()
        if len(compacted) <= limit:
            return compacted

        sentence_matches = list(re.finditer(r"[^.!?]+[.!?]?", compacted))
        query_weights = self._query_weights(query)
        if not sentence_matches or not query_weights:
            return compacted[:limit].rstrip() + "..."

        best_index = 0
        best_score = -1
        for index, match in enumerate(sentence_matches):
            sentence = match.group(0).lower()
            score = sum(weight for stem, weight in query_weights.items() if stem in sentence)
            if score > best_score:
                best_index = index
                best_score = score

        start_index = max(0, best_index - 2)
        end_index = min(len(sentence_matches), best_index + 4)
        focused = "".join(match.group(0) for match in sentence_matches[start_index:end_index]).strip()
        if len(focused) <= limit:
            return focused

        best_match = sentence_matches[best_index]
        start = max(0, best_match.start() - limit // 3)
        end = min(len(compacted), start + limit)
        start = max(0, end - limit)
        prefix = "..." if start > 0 else ""
        suffix = "..." if end < len(compacted) else ""
        return prefix + compacted[start:end].strip() + suffix

    def _item_focus_score(self, item: dict[str, Any], query_weights: dict[str, int]) -> tuple[int, float]:
        text = " ".join(
            str(value or "")
            for value in (
                item.get("section_title"),
                item.get("snippet"),
                item.get("chunk_text"),
            )
        ).lower()
        score = sum(weight for stem, weight in query_weights.items() if stem in text)
        rank = float(item.get("rank") or 999)
        return score, -rank

    def _query_weights(self, query: str) -> dict[str, int]:
        terms = re.findall(r"[A-Za-z][A-Za-z']+", query.lower())
        stop_words = {
            "about",
            "from",
            "have",
            "that",
            "tell",
            "there",
            "this",
            "what",
            "when",
            "where",
            "which",
            "with",
        }
        name_words = {"brenton", "brunton", "maharshi", "paul", "ramana"}
        weights: dict[str, int] = {}
        for term in terms:
            if len(term) < 4 or term in stop_words:
                continue
            weights[term[:7]] = 1 if term in name_words else 3

        query_lower = query.lower()
        if "impression" in query_lower or "perceiv" in query_lower:
            weights.update(
                {
                    "impress": 4,
                    "perceiv": 4,
                    "reactio": 3,
                    "peace": 3,
                    "quiet": 3,
                    "restful": 2,
                }
            )
        return weights

    def _citation_label(self, item: dict[str, Any]) -> str:
        page = ""
        if item.get("page_start") is not None:
            page = f", page {item['page_start']}"
            if item.get("page_end") and item["page_end"] != item["page_start"]:
                page += f"-{item['page_end']}"
        section = f", section {item['section_title']}" if item.get("section_title") else ""
        return (
            f"[Source rank {item.get('rank')}, title {item.get('title')}, "
            f"chunk {item.get('chunk_index')}{page}{section}]"
        )
