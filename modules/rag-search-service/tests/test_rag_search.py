import logging

import httpx
import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.constants import EmbeddingProviderName
from app.db import models  # noqa: F401
from app.db.session import Base, SessionLocal, engine
from app.main import _log_ollama_startup_check, app
from app.schemas.search_request import SearchRequest
from app.services.hybrid_search_service import HybridSearchService
from app.services.embedding_providers.ollama_dependency import (
    OllamaDependencyError,
    ollama_unavailable_error,
)
from app.services.embedding_providers.ollama_provider import OllamaEmbeddingProvider
from app.services.search_service import SearchService


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def _settings(**overrides) -> Settings:
    defaults = {
        "EMBEDDING_PROVIDER": EmbeddingProviderName.OPENAI,
        "EMBEDDING_MODEL": "text-embedding-3-small",
        "EMBEDDING_DIMENSION": 1536,
        "ALLOW_FAKE_EMBEDDINGS": True,
        "SEARCH_MAX_TOP_K": 10,
    }
    defaults.update(overrides)
    return Settings(**defaults)


class FakeRepository:
    def __init__(self):
        self.vector_called = False
        self.keyword_called = False

    def vector_search(self, **kwargs):
        self.vector_called = True
        return [
            {
                "chunk_id": "chunk-vector",
                "resource_id": "resource-1",
                "chunk_index": 0,
                "chunk_text": "Claim submission timeline is thirty days.",
                "title": "Claims Policy",
                "heading_path": ["Claims"],
                "vector_score": 0.92,
                "resource_metadata": {"department": "Claims"},
                "chunk_metadata": {"kind": "policy"},
            }
        ]

    def keyword_search(self, **kwargs):
        self.keyword_called = True
        return [
            {
                "chunk_id": "chunk-keyword",
                "resource_id": "resource-1",
                "chunk_index": 1,
                "chunk_text": "Submission must include all claim documents.",
                "title": "Claims Policy",
                "heading_path": ["Claims"],
                "keyword_score": 3.0,
                "resource_metadata": {},
                "chunk_metadata": {},
            }
        ]


class FakeProvider:
    provider_name = "openai"
    model = "text-embedding-3-small"

    def __init__(self):
        self.calls = []

    def embed_texts(self, texts):
        self.calls.append(list(texts))
        return [[0.1] * 1536 for _ in texts]


def test_search_ui_endpoint():
    with TestClient(app) as client:
        response = client.get("/ui/search")

    assert response.status_code == 200
    assert "RAG Search" in response.text


def test_search_request_rejects_blank_query():
    with TestClient(app) as client:
        response = client.post("/rag/search", json={"query": "   "})

    assert response.status_code == 422


def test_search_rejects_top_k_above_configured_max():
    with TestClient(app) as client:
        response = client.post("/rag/search", json={"query": "claims", "top_k": 999})

    assert response.status_code == 400
    assert "top_k" in response.json()["detail"]


def test_search_endpoint_returns_actionable_ollama_error(monkeypatch):
    def fail_search(self, request):
        del self, request
        raise ollama_unavailable_error(base_url="http://127.0.0.1:11434", model="nomic-embed-text")

    monkeypatch.setattr("app.api.rag_search_routes.SearchService.search", fail_search)

    with TestClient(app) as client:
        response = client.post("/rag/search", json={"query": "claims"})

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "code": "ollama_unavailable",
        "message": (
            "Ollama is unavailable at http://127.0.0.1:11434. Start Ollama, then make sure the "
            "'nomic-embed-text' model is installed with `ollama pull nomic-embed-text`."
        ),
        "details": {"dependency": "ollama", "model": "nomic-embed-text"},
    }


def test_embedding_provider_converts_connection_failure_to_actionable_error(monkeypatch):
    request = httpx.Request("POST", "http://127.0.0.1:11434/api/embed")

    class FailingClient:
        def __init__(self, timeout):
            del timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, json):
            del url, json
            raise httpx.ConnectError("connection refused", request=request)

    monkeypatch.setattr("app.services.embedding_providers.ollama_provider.httpx.Client", FailingClient)
    provider = OllamaEmbeddingProvider(base_url="http://127.0.0.1:11434", model="nomic-embed-text")

    with pytest.raises(OllamaDependencyError, match="ollama pull nomic-embed-text"):
        provider.embed_texts(["claims"])


def test_embedding_startup_check_logs_actionable_ollama_failure(monkeypatch, caplog):
    def unavailable(**kwargs):
        raise ollama_unavailable_error(base_url=kwargs["base_url"], model=kwargs["model"])

    monkeypatch.setattr("app.main.check_ollama_available", unavailable)
    settings = _settings(
        EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA,
        EMBEDDING_MODEL="nomic-embed-text",
        EMBEDDING_DIMENSION=768,
    )

    with caplog.at_level(logging.ERROR, logger="app.main"):
        _log_ollama_startup_check(settings)

    assert "Ollama embedding startup check failed" in caplog.text
    assert "ollama pull nomic-embed-text" in caplog.text


def test_keyword_mode_does_not_call_embedding_provider(monkeypatch):
    def fail_build(settings):
        raise AssertionError("keyword mode must not embed the query")

    monkeypatch.setattr("app.services.search_service.EmbeddingProviderFactory.build", fail_build)

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword"))
        repository = FakeRepository()
        service.repository = repository
        response = service.search(SearchRequest(query="claim submission", search_mode="keyword", top_k=5))
    finally:
        db.close()

    assert repository.keyword_called is True
    assert repository.vector_called is False
    assert response.total_results == 1
    assert response.results[0].keyword_score == 3.0
    assert response.results[0].vector_score is None


def test_vector_mode_embeds_query(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.search_service.EmbeddingProviderFactory.build", lambda settings: provider)

    db = SessionLocal()
    try:
        service = SearchService(db, _settings())
        repository = FakeRepository()
        service.repository = repository
        response = service.search(SearchRequest(query="claim submission", search_mode="vector", top_k=5))
    finally:
        db.close()

    assert provider.calls == [["claim submission"]]
    assert repository.vector_called is True
    assert repository.keyword_called is False
    assert response.results[0].vector_score == 0.92


def test_hybrid_mode_merges_vector_and_keyword_results(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.search_service.EmbeddingProviderFactory.build", lambda settings: provider)

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_VECTOR_WEIGHT=0.7, SEARCH_KEYWORD_WEIGHT=0.3))
        repository = FakeRepository()
        service.repository = repository
        response = service.search(SearchRequest(query="claim submission", search_mode="hybrid", top_k=5))
    finally:
        db.close()

    assert repository.vector_called is True
    assert repository.keyword_called is True
    assert response.search_mode == "hybrid"
    assert response.total_results == 2
    assert {item.chunk_id for item in response.results} == {"chunk-vector", "chunk-keyword"}


def test_hybrid_mode_oversamples_vector_and_keyword_candidates(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.search_service.EmbeddingProviderFactory.build", lambda settings: provider)

    class OversamplingRepository(FakeRepository):
        def __init__(self):
            super().__init__()
            self.vector_top_k = None
            self.keyword_top_k = None

        def vector_search(self, **kwargs):
            self.vector_top_k = kwargs["top_k"]
            return super().vector_search(**kwargs)

        def keyword_search(self, **kwargs):
            self.keyword_top_k = kwargs["top_k"]
            return super().keyword_search(**kwargs)

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_MAX_TOP_K=10, HYBRID_OVERSAMPLING_FACTOR=5))
        repository = OversamplingRepository()
        service.repository = repository
        service.search(SearchRequest(query="claim submission", search_mode="hybrid", top_k=10))
    finally:
        db.close()

    assert repository.vector_top_k == 50
    assert repository.keyword_top_k == 50


def test_hybrid_rrf_rewards_candidates_found_by_both_retrievers():
    results = HybridSearchService().merge(
        vector_results=[
            {"chunk_id": "vector-only", "resource_id": "r1", "chunk_index": 0, "chunk_text": "vector", "vector_score": 0.99},
            {"chunk_id": "both", "resource_id": "r1", "chunk_index": 1, "chunk_text": "both", "vector_score": 0.80},
        ],
        keyword_results=[
            {"chunk_id": "both", "resource_id": "r1", "chunk_index": 1, "chunk_text": "both", "keyword_score": 10.0},
            {"chunk_id": "keyword-only", "resource_id": "r1", "chunk_index": 2, "chunk_text": "keyword", "keyword_score": 9.0},
        ],
        vector_weight=0.7,
        keyword_weight=0.3,
        fusion_strategy="rrf",
        rrf_k=60,
    )

    by_id = {item["chunk_id"]: item for item in results}
    assert by_id["both"]["score"] > by_id["vector-only"]["score"]
    assert by_id["both"]["score"] > by_id["keyword-only"]["score"]


def test_conversational_title_query_promotes_keyword_match(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.search_service.EmbeddingProviderFactory.build", lambda settings: provider)

    class TitleRepository(FakeRepository):
        def vector_search(self, **kwargs):
            self.vector_called = True
            return [
                {
                    "chunk_id": "unrelated-vector",
                    "resource_id": "resource-2",
                    "chunk_index": 0,
                    "chunk_text": "A clinic conversation in another novel.",
                    "title": "Tender is the Night",
                    "heading_path": [],
                    "vector_score": 0.55,
                    "resource_metadata": {},
                    "chunk_metadata": {},
                }
            ]

        def keyword_search(self, **kwargs):
            self.keyword_called = True
            assert kwargs["query"] == "frankenstein"
            return [
                {
                    "chunk_id": "frankenstein-title",
                    "resource_id": "resource-frankenstein",
                    "chunk_index": 0,
                    "chunk_text": "Frankenstein by Mary Shelley.",
                    "title": "frankenstein",
                    "heading_path": [],
                    "keyword_score": 10.0,
                    "resource_metadata": {"author": "Mary Shelley"},
                    "chunk_metadata": {},
                }
            ]

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_VECTOR_WEIGHT=0.7, SEARCH_KEYWORD_WEIGHT=0.3))
        service.repository = TitleRepository()
        response = service.search(SearchRequest(query="tell me about frankenstein", search_mode="hybrid", top_k=5))
    finally:
        db.close()

    assert response.query == "frankenstein"
    assert response.query_intent == "summary_request"
    assert response.results[0].title == "frankenstein"


def test_query_understanding_normalizes_configured_typos(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.search_service.EmbeddingProviderFactory.build", lambda settings: provider)

    class AliasRepository(FakeRepository):
        def keyword_search(self, **kwargs):
            self.keyword_called = True
            assert kwargs["query"] == "A Christmas Carol"
            return [
                {
                    "chunk_id": "christmas-title",
                    "resource_id": "christmas",
                    "chunk_index": 0,
                    "chunk_text": "A Christmas Carol by Charles Dickens.",
                    "title": "A Christmas Carol",
                    "heading_path": [],
                    "keyword_score": 10.0,
                    "resource_metadata": {},
                    "chunk_metadata": {},
                }
            ]

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword"))
        service.repository = AliasRepository()
        response = service.search(SearchRequest(query="tell me about the novel: A Christams Carol", search_mode="keyword", top_k=1))
    finally:
        db.close()

    assert response.query == "A Christmas Carol"
    assert response.spelling_normalized is True
    assert response.results[0].title == "A Christmas Carol"


def test_query_understanding_supports_runtime_aliases(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.search_service.EmbeddingProviderFactory.build", lambda settings: provider)

    class AliasRepository(FakeRepository):
        def keyword_search(self, **kwargs):
            assert kwargs["query"] == "customer policy"
            return [
                {
                    "chunk_id": "policy",
                    "resource_id": "resource-1",
                    "chunk_index": 1,
                    "chunk_text": "Customer policy requirements.",
                    "title": "Customer Policy",
                    "heading_path": [],
                    "keyword_score": 5.0,
                    "resource_metadata": {},
                    "chunk_metadata": {},
                }
            ]

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword", QUERY_ALIASES={"custmr": "customer"}))
        service.repository = AliasRepository()
        response = service.search(SearchRequest(query="custmr policy", search_mode="keyword", top_k=1))
    finally:
        db.close()

    assert response.query == "customer policy"
    assert response.spelling_normalized is True


def test_conversational_subject_prefix_is_removed(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.search_service.EmbeddingProviderFactory.build", lambda settings: provider)

    class TitleRepository(FakeRepository):
        def keyword_search(self, **kwargs):
            assert kwargs["query"] == "A Christmas Carol"
            return [
                {
                    "chunk_id": "christmas-title",
                    "resource_id": "christmas",
                    "chunk_index": 0,
                    "chunk_text": "A Christmas Carol by Charles Dickens.",
                    "title": "A Christmas Carol",
                    "heading_path": [],
                    "keyword_score": 10.0,
                    "resource_metadata": {},
                    "chunk_metadata": {},
                }
            ]

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword"))
        service.repository = TitleRepository()
        response = service.search(SearchRequest(query="tell me about the novel: A Christmas Carol", search_mode="keyword", top_k=1))
    finally:
        db.close()

    assert response.query == "A Christmas Carol"
    assert response.results[0].title == "A Christmas Carol"


def test_exact_quote_intent_is_passed_to_keyword_search(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.search_service.EmbeddingProviderFactory.build", lambda settings: provider)

    class QuoteRepository(FakeRepository):
        def keyword_search(self, **kwargs):
            assert kwargs["query_intent"] == "exact_quote"
            assert kwargs["query"] == "The very gold and silver fish, set forth among these choice fruits in a bowl"
            return [
                {
                    "chunk_id": "quote",
                    "resource_id": "christmas",
                    "chunk_index": 24,
                    "chunk_text": "The very gold and silver fish, set forth among these choice fruits in a bowl.",
                    "title": "A Christmas Carol",
                    "heading_path": [],
                    "keyword_score": 8.0,
                    "resource_metadata": {},
                    "chunk_metadata": {},
                }
            ]

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword"))
        service.repository = QuoteRepository()
        response = service.search(
            SearchRequest(
                query='"The very gold and silver fish, set forth among these choice fruits in a bowl"',
                search_mode="keyword",
                top_k=1,
            )
        )
    finally:
        db.close()

    assert response.query_intent == "exact_quote"
    assert response.results[0].chunk_id == "quote"


def test_title_match_orders_early_chunks_first():
    db = SessionLocal()
    try:
        from app.db.models import RagDocumentChunk, RagIngestionJob, Resource

        resource_id = "00000000-0000-0000-0000-000000000501"
        job_id = "00000000-0000-0000-0000-000000000502"
        later_chunk_id = "00000000-0000-0000-0000-000000000503"
        first_chunk_id = "00000000-0000-0000-0000-000000000504"
        resource = Resource(resource_id=resource_id, title="frankenstein", rag_enabled=True, ingestion_status="READY")
        db.add_all(
            [
                resource,
                RagIngestionJob(job_id=job_id, resource_id=resource_id, status="COMPLETED", async_backend="test"),
            ]
        )
        db.flush()
        db.add_all(
            [
                RagDocumentChunk(
                    chunk_id=later_chunk_id,
                    resource_id=resource.resource_id,
                    job_id=job_id,
                    chunk_index=7,
                    chunk_text="Frankenstein Frankenstein Frankenstein later footer.",
                    chunk_hash_sha256="later",
                    token_count=4,
                    char_count=45,
                ),
                RagDocumentChunk(
                    chunk_id=first_chunk_id,
                    resource_id=resource.resource_id,
                    job_id=job_id,
                    chunk_index=0,
                    chunk_text="Frankenstein by Mary Shelley.",
                    chunk_hash_sha256="first",
                    token_count=4,
                    char_count=28,
                ),
            ]
        )
        db.commit()

        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword"))
        response = service.search(SearchRequest(query="tell me about frankenstein", search_mode="keyword", top_k=2))
    finally:
        db.close()

    assert [item.chunk_id for item in response.results] == [first_chunk_id, later_chunk_id]


def test_question_reranking_prefers_direct_evidence_over_title_front_matter():
    class QuestionRepository(FakeRepository):
        def keyword_search(self, **kwargs):
            self.keyword_called = True
            return [
                {
                    "chunk_id": "front-matter",
                    "resource_id": "ramana",
                    "chunk_index": 0,
                    "chunk_text": "7th Impression 1977. Ramana Maharshi by Paul Brunton.",
                    "title": "Ramana Maharshi by Paul Brenton",
                    "heading_path": [],
                    "keyword_score": 50.0,
                    "resource_match_score": 2.0,
                    "resource_metadata": {},
                    "chunk_metadata": {},
                },
                {
                    "chunk_id": "direct-evidence",
                    "resource_id": "ramana",
                    "chunk_index": 8,
                    "chunk_text": (
                        "I perceive that a great peace is penetrating the inner reaches of my being. "
                        "The mysterious peace which has arisen within me is my reaction to the personality "
                        "of the Maharshi."
                    ),
                    "title": "Ramana Maharshi by Paul Brenton",
                    "heading_path": ["THE HILL OF THE HOLY BEACON"],
                    "keyword_score": 20.0,
                    "resource_match_score": 1.0,
                    "resource_metadata": {},
                    "chunk_metadata": {},
                },
            ]

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword"))
        service.repository = QuestionRepository()
        response = service.search(
            SearchRequest(
                query="what was the impression perceived by Paul Brenton when he met Ramana Maharshi?",
                search_mode="keyword",
                top_k=2,
            )
        )
    finally:
        db.close()

    assert response.results[0].chunk_id == "direct-evidence"


def test_keyword_ignores_stopword_noise_and_promotes_exact_phrase():
    db = SessionLocal()
    try:
        from app.db.models import RagDocumentChunk, RagIngestionJob, Resource

        christmas_resource_id = "00000000-0000-0000-0000-000000000511"
        ramayan_resource_id = "00000000-0000-0000-0000-000000000512"
        christmas_job_id = "00000000-0000-0000-0000-000000000513"
        ramayan_job_id = "00000000-0000-0000-0000-000000000514"
        christmas_chunk_id = "00000000-0000-0000-0000-000000000515"
        ramayan_chunk_id = "00000000-0000-0000-0000-000000000516"
        christmas = Resource(
            resource_id=christmas_resource_id,
            title="A Christmas Carol",
            rag_enabled=True,
            ingestion_status="READY",
            resource_metadata={"author": "Charles Dickens"},
        )
        ramayan = Resource(resource_id=ramayan_resource_id, title="Ramayan", rag_enabled=True, ingestion_status="READY")
        db.add_all(
            [
                christmas,
                ramayan,
                RagIngestionJob(
                    job_id=christmas_job_id,
                    resource_id=christmas_resource_id,
                    status="COMPLETED",
                    async_backend="test",
                ),
                RagIngestionJob(
                    job_id=ramayan_job_id,
                    resource_id=ramayan_resource_id,
                    status="COMPLETED",
                    async_backend="test",
                ),
            ]
        )
        db.flush()
        db.add_all(
            [
                RagDocumentChunk(
                    chunk_id=christmas_chunk_id,
                    resource_id=christmas.resource_id,
                    job_id=christmas_job_id,
                    chunk_index=24,
                    chunk_text=(
                        "The very gold and silver fish, set forth among these choice fruits in a bowl, "
                        "though members of a dull and stagnant-blooded race, appeared to know that "
                        "there was something going on."
                    ),
                    chunk_hash_sha256="christmas-exact",
                    token_count=30,
                    char_count=190,
                ),
                RagDocumentChunk(
                    chunk_id=ramayan_chunk_id,
                    resource_id=ramayan.resource_id,
                    job_id=ramayan_job_id,
                    chunk_index=0,
                    chunk_text=" ".join(["the and of in that there was something"] * 200),
                    chunk_hash_sha256="ramayan-common-words",
                    token_count=1600,
                    char_count=7600,
                ),
            ]
        )
        db.commit()

        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword"))
        response = service.search(
            SearchRequest(
                query=(
                    "The very gold and silver fish, set forth among these choice fruits in a bowl, "
                    "though members of a dull and stagnant-blooded race, appeared to know that "
                    "there was something going on"
                ),
                search_mode="keyword",
                top_k=2,
            )
        )
    finally:
        db.close()

    assert response.results[0].chunk_id == christmas_chunk_id
    assert all(item.chunk_id != ramayan_chunk_id for item in response.results)


def test_hybrid_does_not_force_high_raw_keyword_score_above_exact_title(monkeypatch):
    provider = FakeProvider()
    monkeypatch.setattr("app.services.search_service.EmbeddingProviderFactory.build", lambda settings: provider)

    class ChristmasRepository(FakeRepository):
        def vector_search(self, **kwargs):
            self.vector_called = True
            return [
                {
                    "chunk_id": "christmas-title",
                    "resource_id": "christmas",
                    "chunk_index": 0,
                    "chunk_text": "A Christmas Carol by Charles Dickens.",
                    "title": "A Christmas Carol",
                    "heading_path": [],
                    "vector_score": 0.80,
                    "resource_metadata": {},
                    "chunk_metadata": {},
                }
            ]

        def keyword_search(self, **kwargs):
            self.keyword_called = True
            return [
                {
                    "chunk_id": "junk",
                    "resource_id": "ramayan",
                    "chunk_index": 305,
                    "chunk_text": "Common words repeated many times.",
                    "title": "Ramayan",
                    "heading_path": [],
                    "keyword_score": 700.0,
                    "resource_match_score": 0.0,
                    "resource_metadata": {},
                    "chunk_metadata": {},
                },
                {
                    "chunk_id": "christmas-title",
                    "resource_id": "christmas",
                    "chunk_index": 0,
                    "chunk_text": "A Christmas Carol by Charles Dickens.",
                    "title": "A Christmas Carol",
                    "heading_path": [],
                    "keyword_score": 40.0,
                    "resource_match_score": 2.0,
                    "resource_metadata": {},
                    "chunk_metadata": {},
                },
            ]

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_VECTOR_WEIGHT=0.7, SEARCH_KEYWORD_WEIGHT=0.3))
        service.repository = ChristmasRepository()
        response = service.search(SearchRequest(query="tell me about the novel: A Christmas Carol", search_mode="hybrid", top_k=2))
    finally:
        db.close()

    assert response.results[0].chunk_id == "christmas-title"


def test_search_filters_low_value_result_chunks():
    db = SessionLocal()
    try:
        from app.db.models import RagDocumentChunk, RagIngestionJob, Resource

        resource_id = "00000000-0000-0000-0000-000000000521"
        job_id = "00000000-0000-0000-0000-000000000522"
        publisher_chunk_id = "00000000-0000-0000-0000-000000000523"
        content_chunk_id = "00000000-0000-0000-0000-000000000524"
        resource = Resource(resource_id=resource_id, title="Bhagawat Gita", rag_enabled=True, ingestion_status="READY")
        db.add_all(
            [
                resource,
                RagIngestionJob(job_id=job_id, resource_id=resource_id, status="COMPLETED", async_backend="test"),
            ]
        )
        db.flush()
        db.add_all(
            [
                RagDocumentChunk(
                    chunk_id=publisher_chunk_id,
                    resource_id=resource.resource_id,
                    job_id=job_id,
                    chunk_index=0,
                    chunk_text="Publications Division, T.T.D, Tirupati.",
                    chunk_hash_sha256="publisher",
                    token_count=4,
                    char_count=38,
                ),
                RagDocumentChunk(
                    chunk_id=content_chunk_id,
                    resource_id=resource.resource_id,
                    job_id=job_id,
                    chunk_index=1,
                    chunk_text="The Bhagavad Gita is a conversation between Arjuna and Lord Krishna on duty and spiritual knowledge.",
                    chunk_hash_sha256="content",
                    token_count=15,
                    char_count=100,
                ),
            ]
        )
        db.commit()

        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword"))
        response = service.search(SearchRequest(query="Bhagavad Githa", search_mode="keyword", top_k=5))
    finally:
        db.close()

    assert [item.chunk_id for item in response.results] == [content_chunk_id]


def test_search_filters_chunks_marked_not_searchable():
    class QualityMetadataRepository(FakeRepository):
        def keyword_search(self, **kwargs):
            self.keyword_called = True
            return [
                {
                    "chunk_id": "not-searchable",
                    "resource_id": "resource-1",
                    "chunk_index": 0,
                    "chunk_text": "This text has enough words but was marked as not searchable by ingestion.",
                    "title": "Policy",
                    "heading_path": [],
                    "keyword_score": 5.0,
                    "resource_match_score": 0.0,
                    "resource_metadata": {},
                    "chunk_metadata": {"quality": "filtered", "searchable": False},
                },
                {
                    "chunk_id": "searchable",
                    "resource_id": "resource-1",
                    "chunk_index": 1,
                    "chunk_text": "This searchable policy chunk describes claim submission requirements.",
                    "title": "Policy",
                    "heading_path": [],
                    "keyword_score": 4.0,
                    "resource_match_score": 0.0,
                    "resource_metadata": {},
                    "chunk_metadata": {"quality": "searchable", "searchable": True},
                },
            ]

    db = SessionLocal()
    try:
        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword"))
        service.repository = QualityMetadataRepository()
        response = service.search(SearchRequest(query="claim submission requirements", search_mode="keyword", top_k=5))
    finally:
        db.close()

    assert [item.chunk_id for item in response.results] == ["searchable"]


def test_search_keeps_numeric_table_heavy_chunks_when_enabled():
    class NumericTableRepository(FakeRepository):
        def keyword_search(self, **kwargs):
            self.keyword_called = True
            return [
                {
                    "chunk_id": "invoice-table",
                    "resource_id": "resource-1",
                    "chunk_index": 4,
                    "chunk_text": (
                        "Invoice table | INV-1001 | 2026-06-25 | 1500.75 | CLAIM-8891 "
                        "Invoice table | INV-1002 | 2026-06-26 | 2750.20 | CLAIM-8892"
                    ),
                    "title": "Invoice Register",
                    "heading_path": [],
                    "keyword_score": 6.0,
                    "resource_match_score": 0.0,
                    "resource_metadata": {},
                    "chunk_metadata": {"quality": "searchable", "numeric_table_heavy": True, "searchable": True},
                }
            ]

    db = SessionLocal()
    try:
        service = SearchService(
            db,
            _settings(
                SEARCH_DEFAULT_MODE="keyword",
                SEARCH_KEEP_NUMERIC_TABLE_CHUNKS=True,
                SEARCH_MIN_ALPHA_RATIO=0.70,
            ),
        )
        service.repository = NumericTableRepository()
        response = service.search(SearchRequest(query="CLAIM-8891 INV-1001", search_mode="keyword", top_k=5))
    finally:
        db.close()

    assert [item.chunk_id for item in response.results] == ["invoice-table"]


def test_search_response_strips_page_markers_from_display_text():
    db = SessionLocal()
    try:
        from app.db.models import RagDocumentChunk, RagIngestionJob, Resource

        resource_id = "00000000-0000-0000-0000-000000000531"
        job_id = "00000000-0000-0000-0000-000000000532"
        chunk_id = "00000000-0000-0000-0000-000000000533"
        resource = Resource(resource_id=resource_id, title="Policy", rag_enabled=True, ingestion_status="READY")
        db.add_all(
            [
                resource,
                RagIngestionJob(job_id=job_id, resource_id=resource_id, status="COMPLETED", async_backend="test"),
            ]
        )
        db.flush()
        db.add(
            RagDocumentChunk(
                chunk_id=chunk_id,
                resource_id=resource.resource_id,
                job_id=job_id,
                chunk_index=0,
                chunk_text="[Page 12]\nPolicy content has claim submission rules.",
                chunk_hash_sha256="chunk-1",
                token_count=6,
                char_count=50,
                page_start=12,
                page_end=12,
            )
        )
        db.commit()

        service = SearchService(db, _settings(SEARCH_DEFAULT_MODE="keyword"))
        response = service.search(SearchRequest(query="claim submission", search_mode="keyword", top_k=1, include_chunk_text=True))
    finally:
        db.close()

    assert response.results[0].page_start == 12
    assert "[Page 12]" not in response.results[0].snippet
    assert "[Page 12]" not in response.results[0].chunk_text


def test_search_api_returns_empty_result_without_rows():
    with TestClient(app) as client:
        response = client.post(
            "/rag/search",
            json={"query": "anything", "search_mode": "keyword", "top_k": 3, "include_chunk_text": False},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total_results"] == 0
    assert body["results"] == []
