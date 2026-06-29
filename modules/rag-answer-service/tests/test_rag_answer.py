from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import app
from app.schemas.answer_request import AnswerRequest
from app.services.answer_service import AnswerService
from app.services.context_builder import ContextBuilder
from app.services.llm_providers.factory import LlmProviderFactory
from app.services.llm_providers.gemini_provider import GeminiLlmProvider


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
        return "A great peace was penetrating the inner reaches of his being. [Source rank 1, chunk 8, page 19]"


class ModelEchoProvider(FakeProvider):
    provider_name = "fake"

    def __init__(self, model):
        super().__init__()
        self.model = model

    def generate(self, prompt):
        self.prompt = prompt
        return f"{self.model} says a great peace was felt. [Source rank 1, chunk 8, page 19]"


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

    assert response.answer_status == "answered"
    assert "Source rank 1, chunk 8, page 19" in response.answer
    assert response.cited_source_ranks == [1]
    assert response.citation_verification["supported"] is True
    assert response.context_source_count == 1
    assert response.sources[0].page_start == 19
    assert "A great peace" in provider.prompt
    assert "Citation rules" in provider.prompt


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
    assert response.answer_status == "insufficient_context"
    assert response.citation_verification["reason"] == "no_selected_context"
    assert provider.prompt is None


def test_answer_service_rejects_unsupported_uncited_answer(monkeypatch):
    class UnsupportedProvider(FakeProvider):
        def generate(self, prompt):
            self.prompt = prompt
            return "He later founded a new monastery in another city."

    provider = UnsupportedProvider()
    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", lambda settings: provider)

    service = AnswerService(Settings())
    service.search_client = FakeSearchClient()
    response = service.answer(AnswerRequest(query="What did he feel?", top_k=5, context_top_k=1))

    assert response.answer_status == "insufficient_context"
    assert "could not verify" in response.answer
    assert response.citation_verification["reason"] == "answer_has_no_source_rank_citations"


def test_answer_service_rejects_wrong_chunk_citation(monkeypatch):
    class WrongChunkProvider(FakeProvider):
        def generate(self, prompt):
            self.prompt = prompt
            return "He felt peace in Maharshi's presence. [Source rank 1, chunk 99, page 19]"

    provider = WrongChunkProvider()
    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", lambda settings: provider)

    service = AnswerService(Settings())
    service.search_client = FakeSearchClient()
    response = service.answer(AnswerRequest(query="What did he feel?", top_k=5, context_top_k=1))

    assert response.answer_status == "insufficient_context"
    assert response.citation_verification["reason"] == "answer_cites_wrong_chunk_for_source_rank"


def test_answer_service_rejects_answer_when_named_query_subject_is_missing(monkeypatch):
    class HallucinatingProvider(FakeProvider):
        def generate(self, prompt):
            self.prompt = prompt
            return "Paul Brenton felt awe when he met Ramana Maharshi. [Source rank 1, chunk 8, page 19]"

    provider = HallucinatingProvider()
    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", lambda settings: provider)

    service = AnswerService(Settings())
    service.search_client = FakeSearchClient()
    response = service.answer(
        AnswerRequest(query="what was the impression perceived by Paul Brenton when he met Ramana Maharshi?")
    )

    assert response.answer_status == "insufficient_context"
    assert response.citation_verification["reason"] == "query_named_anchors_not_found_in_selected_context"


def test_answer_service_rejects_inference_language(monkeypatch):
    class InferenceProvider(FakeProvider):
        def generate(self, prompt):
            self.prompt = prompt
            return (
                "It can be inferred that he felt peace from the passage. "
                "[Source rank 1, chunk 8, page 19]"
            )

    provider = InferenceProvider()
    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", lambda settings: provider)

    service = AnswerService(Settings())
    service.search_client = FakeSearchClient()
    response = service.answer(AnswerRequest(query="What did he feel?"))

    assert response.answer_status == "insufficient_context"
    assert response.citation_verification["reason"] == "answer_uses_unsupported_inference_language"


def test_answer_service_supports_modes_and_raw_prompt(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", lambda settings: provider)

    service = AnswerService(Settings())
    service.search_client = FakeSearchClient()
    response = service.answer(
        AnswerRequest(
            query="What did he feel?",
            answer_mode="quote-backed",
            include_raw_prompt=True,
            top_k=5,
            context_top_k=1,
        )
    )

    assert response.answer_mode == "quote-backed"
    assert response.raw_prompt is not None
    assert "Prefer short direct quotations" in response.raw_prompt


def test_answer_service_uses_configured_synthesis_prompt(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", lambda settings: provider)

    service = AnswerService(Settings(ANSWER_SYNTHESIS_INSTRUCTION="Combine every relevant chunk before answering."))
    service.search_client = FakeSearchClient()
    response = service.answer(
        AnswerRequest(
            query="What did he feel?",
            include_raw_prompt=True,
            top_k=5,
            context_top_k=1,
        )
    )

    assert response.raw_prompt is not None
    assert "Combine every relevant chunk before answering." in response.raw_prompt


def test_answer_observability_is_config_gated(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", lambda settings: provider)

    service = AnswerService(Settings(ANSWER_OBSERVABILITY_ENABLED=True))
    service.search_client = FakeSearchClient()
    response = service.answer(AnswerRequest(query="What did he feel?", top_k=5, context_top_k=1))

    assert response.observability is not None
    assert response.observability["timings_ms"]["context_packing_ms"] >= 0
    assert response.observability["selected_sources"][0]["chunk_index"] == 8


def test_answer_compare_uses_same_context_for_multiple_models(monkeypatch):
    built_models = []

    def build_provider(settings):
        model = settings.gemini_model if settings.llm_provider == "gemini" else settings.llm_model
        built_models.append((settings.llm_provider, model))
        provider = ModelEchoProvider(model)
        provider.provider_name = settings.llm_provider
        return provider

    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", build_provider)

    service = AnswerService(Settings(ANSWER_COMPARE_MODELS="mistral:latest,gemini:gemini-2.5-flash", GEMINI_API_KEY="test-key"))
    service.search_client = FakeSearchClient()
    response = service.compare(AnswerRequest(query="What did he feel?", top_k=5, context_top_k=1))

    assert built_models == [("ollama", "mistral:latest"), ("gemini", "gemini-2.5-flash")]
    assert response.models == ["ollama:mistral:latest", "gemini:gemini-2.5-flash"]
    assert len(response.results) == 2
    assert {result.answer_status for result in response.results} == {"answered"}
    assert all("Source rank 1, chunk 8, page 19" in result.answer for result in response.results)
    assert response.context_source_count == 1
    assert response.sources[0].chunk_index == 8


def test_answer_compare_returns_failed_card_for_model_error(monkeypatch):
    def build_provider(settings):
        if settings.llm_model == "missing-model":
            raise RuntimeError("model not found")
        return ModelEchoProvider(settings.llm_model)

    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", build_provider)

    service = AnswerService(Settings())
    service.search_client = FakeSearchClient()
    response = service.compare(
        AnswerRequest(
            query="What did he feel?",
            top_k=5,
            context_top_k=1,
            compare_models=["mistral:latest", "missing-model"],
        )
    )

    assert [result.llm_model for result in response.results] == ["mistral:latest", "missing-model"]
    assert response.results[0].answer_status == "answered"
    assert response.results[1].answer_status == "failed"
    assert "model not found" in response.results[1].answer


def test_answer_compare_returns_failed_card_when_gemini_key_missing(monkeypatch):
    service = AnswerService(Settings(GEMINI_API_KEY=""))
    service.search_client = FakeSearchClient()
    response = service.compare(
        AnswerRequest(
            query="What did he feel?",
            top_k=5,
            context_top_k=1,
            compare_models=["gemini:gemini-2.5-flash"],
        )
    )

    assert response.models == ["gemini:gemini-2.5-flash"]
    assert response.results[0].llm_provider == "gemini"
    assert response.results[0].llm_model == "gemini-2.5-flash"
    assert response.results[0].answer_status == "failed"
    assert "GEMINI_API_KEY" in response.results[0].answer


def test_answer_compare_stream_emits_search_then_each_model(monkeypatch):
    def build_provider(settings):
        return ModelEchoProvider(settings.llm_model)

    monkeypatch.setattr("app.services.answer_service.LlmProviderFactory.build", build_provider)

    service = AnswerService(Settings(ANSWER_COMPARE_MODELS="mistral:latest,gemma4"))
    service.search_client = FakeSearchClient()
    events = list(service.compare_stream(AnswerRequest(query="What did he feel?", top_k=5, context_top_k=1)))

    assert [event["event"] for event in events] == [
        "search_complete",
        "model_started",
        "model_result",
        "model_started",
        "model_result",
        "complete",
    ]
    assert events[0]["models"] == ["ollama:mistral:latest", "ollama:gemma4"]
    assert events[1]["model"] == "ollama:mistral:latest"
    assert events[2]["result"]["llm_model"] == "mistral:latest"
    assert events[3]["model"] == "ollama:gemma4"
    assert events[4]["result"]["llm_model"] == "gemma4"
    assert events[5]["completed"] == 2


def test_gemini_provider_factory_and_payload(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"candidates": [{"content": {"parts": [{"text": "Gemini answer"}]}}]}

    class FakeClient:
        def __init__(self, timeout):
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, params, json):
            captured["url"] = url
            captured["params"] = params
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.llm_providers.gemini_provider.httpx.Client", FakeClient)

    settings = Settings(LLM_PROVIDER="gemini", GEMINI_API_KEY="test-key", GEMINI_MODEL="gemini-2.5-flash")
    provider = LlmProviderFactory.build(settings)

    assert isinstance(provider, GeminiLlmProvider)
    assert provider.generate("Hello") == "Gemini answer"
    assert captured["url"].endswith("/models/gemini-2.5-flash:generateContent")
    assert captured["params"] == {"key": "test-key"}
    assert captured["json"]["contents"][0]["parts"][0]["text"] == "Hello"


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
