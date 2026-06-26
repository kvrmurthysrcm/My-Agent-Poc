from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.schemas.answer_request import AnswerRequest
from app.services.answer_service import AnswerService
from app.services.context_builder import ContextBuilder


def _fake_search_response():
    return {
        "query": "Ramana Maharshi",
        "search_mode": "hybrid",
        "total_results": 1,
        "results": [
            {
                "rank": 1,
                "resource_id": "resource-1",
                "chunk_id": "chunk-1",
                "title": "Ramana Maharshi by Paul Brenton",
                "chunk_index": 8,
                "page_start": 19,
                "page_end": 21,
                "section_title": "THE HILL OF THE HOLY BEACON",
                "score": 0.9,
                "snippet": "A great peace is penetrating the inner reaches of my being.",
                "chunk_text": "A great peace is penetrating the inner reaches of my being.",
            }
        ],
    }


class FakeSearchClient:
    def search(self, request):
        return _fake_search_response()


class FakeProvider:
    provider_name = "fake"
    model = "fake-model"

    def __init__(self):
        self.prompt = None

    def generate(self, prompt):
        self.prompt = prompt
        return "He felt a deep quietness and peace in Maharshi's presence."


def test_answer_ui_endpoint():
    with TestClient(app) as client:
        response = client.get("/ui/answer")

    assert response.status_code == 200
    assert "RAG Answer" in response.text


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_answer_service_uses_search_context_and_returns_sources(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", lambda settings: provider)

    service = AnswerService(Settings())
    service.search_client = FakeSearchClient()
    response = service.answer(AnswerRequest(query="What did he feel?", top_k=5, context_top_k=1))

    assert response.answer == "He felt a deep quietness and peace in Maharshi's presence."
    assert response.context_source_count == 1
    assert response.sources[0].page_start == 19
    assert "A great peace" in provider.prompt


def test_answer_service_does_not_guess_without_context(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", lambda settings: provider)

    class EmptySearchClient:
        def search(self, request):
            return {"query": request.query, "search_mode": "hybrid", "total_results": 0, "results": []}

    service = AnswerService(Settings())
    service.search_client = EmptySearchClient()
    response = service.answer(AnswerRequest(query="Unknown question"))

    assert "could not find enough retrieved context" in response.answer
    assert provider.prompt is None


def test_context_builder_preserves_later_ranked_sources_under_budget():
    response = {
        "results": [
            {
                "rank": 1,
                "title": "Large opening chunk",
                "chunk_index": 0,
                "chunk_text": "Opening filler. " * 300,
            },
            {
                "rank": 2,
                "title": "Large middle chunk",
                "chunk_index": 1,
                "chunk_text": "Middle filler. " * 300,
            },
            {
                "rank": 3,
                "title": "Relevant later chunk",
                "chunk_index": 8,
                "chunk_text": (
                    "Unrelated opening. " * 120
                    + "I perceive that a great peace is penetrating the inner reaches of my being. "
                    + "That is my reaction to the personality of the Maharshi."
                ),
            },
        ]
    }

    context, selected = ContextBuilder().build(
        search_response=response,
        context_top_k=3,
        max_chars=1800,
        query="what impression did Paul Brenton perceive when he met Ramana Maharshi",
        max_chars_per_source=900,
    )

    assert sorted(item["rank"] for item in selected) == [1, 2, 3]
    assert selected[0]["rank"] == 3
    assert "great peace is penetrating" in context
