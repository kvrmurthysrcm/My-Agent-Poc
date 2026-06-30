from typing import Any

import httpx

from app.core.config import Settings
from app.schemas.answer_request import AnswerRequest
from app.trace_context import outbound_trace_headers


class RagSearchClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    def search(self, request: AnswerRequest) -> dict[str, Any]:
        payload = {
            "query": request.query,
            "search_mode": request.search_mode,
            "top_k": request.top_k or self.settings.answer_default_top_k,
            "filters": request.filters.model_dump(),
            "include_metadata": True,
            "include_chunk_text": True,
        }
        endpoint = "search/debug" if self.settings.answer_observability_enabled else "search"
        with httpx.Client(timeout=self.settings.rag_search_timeout_seconds) as client:
            response = client.post(
                f"{self.settings.rag_search_base_url}/rag/{endpoint}",
                json=payload,
                headers=outbound_trace_headers(),
            )
            if response.status_code == 404 and endpoint == "search/debug":
                response = client.post(
                    f"{self.settings.rag_search_base_url}/rag/search",
                    json=payload,
                    headers=outbound_trace_headers(),
                )
            response.raise_for_status()
            return response.json()

    def health(self) -> dict[str, Any]:
        with httpx.Client(timeout=self.settings.rag_search_timeout_seconds) as client:
            response = client.get(f"{self.settings.rag_search_base_url}/health", headers=outbound_trace_headers())
            response.raise_for_status()
            return response.json()
