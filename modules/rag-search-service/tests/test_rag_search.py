from fastapi.testclient import TestClient

from app.core.config import Settings
from app.core.constants import EmbeddingProviderName
from app.db import models  # noqa: F401
from app.db.session import Base, SessionLocal, engine
from app.main import app
from app.schemas.search_request import SearchRequest
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
    assert response.results[0].title == "frankenstein"


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


def test_sqlite_title_match_orders_early_chunks_first():
    db = SessionLocal()
    try:
        from app.db.models import RagDocumentChunk, Resource

        resource = Resource(resource_id="resource-frankenstein", title="frankenstein", rag_enabled=True, ingestion_status="READY")
        db.add(resource)
        db.add_all(
            [
                RagDocumentChunk(
                    chunk_id="later",
                    resource_id=resource.resource_id,
                    job_id="job-1",
                    chunk_index=7,
                    chunk_text="Frankenstein Frankenstein Frankenstein later footer.",
                    chunk_hash_sha256="later",
                    token_count=4,
                    char_count=45,
                ),
                RagDocumentChunk(
                    chunk_id="first",
                    resource_id=resource.resource_id,
                    job_id="job-1",
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

    assert [item.chunk_id for item in response.results] == ["first", "later"]


def test_sqlite_keyword_ignores_stopword_noise_and_promotes_exact_phrase():
    db = SessionLocal()
    try:
        from app.db.models import RagDocumentChunk, Resource

        christmas = Resource(
            resource_id="christmas",
            title="A Christmas Carol",
            rag_enabled=True,
            ingestion_status="READY",
            resource_metadata={"author": "Charles Dickens"},
        )
        ramayan = Resource(resource_id="ramayan", title="Ramayan", rag_enabled=True, ingestion_status="READY")
        db.add_all([christmas, ramayan])
        db.add_all(
            [
                RagDocumentChunk(
                    chunk_id="christmas-exact",
                    resource_id=christmas.resource_id,
                    job_id="job-1",
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
                    chunk_id="ramayan-common-words",
                    resource_id=ramayan.resource_id,
                    job_id="job-2",
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

    assert response.results[0].chunk_id == "christmas-exact"
    assert all(item.chunk_id != "ramayan-common-words" for item in response.results)


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
        from app.db.models import RagDocumentChunk, Resource

        resource = Resource(resource_id="gita", title="Bhagawat Gita", rag_enabled=True, ingestion_status="READY")
        db.add(resource)
        db.add_all(
            [
                RagDocumentChunk(
                    chunk_id="publisher",
                    resource_id=resource.resource_id,
                    job_id="job-1",
                    chunk_index=0,
                    chunk_text="Publications Division, T.T.D, Tirupati.",
                    chunk_hash_sha256="publisher",
                    token_count=4,
                    char_count=38,
                ),
                RagDocumentChunk(
                    chunk_id="content",
                    resource_id=resource.resource_id,
                    job_id="job-1",
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

    assert [item.chunk_id for item in response.results] == ["content"]


def test_search_response_strips_page_markers_from_display_text():
    db = SessionLocal()
    try:
        from app.db.models import RagDocumentChunk, Resource

        resource = Resource(resource_id="resource-1", title="Policy", rag_enabled=True, ingestion_status="READY")
        db.add(resource)
        db.add(
            RagDocumentChunk(
                chunk_id="chunk-1",
                resource_id=resource.resource_id,
                job_id="job-1",
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


def test_search_api_returns_empty_result_for_sqlite_without_rows():
    with TestClient(app) as client:
        response = client.post(
            "/rag/search",
            json={"query": "anything", "search_mode": "keyword", "top_k": 3, "include_chunk_text": False},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["total_results"] == 0
    assert body["results"] == []
