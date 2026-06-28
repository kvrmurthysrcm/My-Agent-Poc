from app.core.config import Settings
from app.core.constants import AsyncBackend, EmbeddingProviderName
from app.services.async_backends.db_worker_dispatcher import DbWorkerDispatcher
from app.services.async_backends.factory import JobDispatcherFactory
from app.services.embedding_providers.factory import EmbeddingProviderFactory
from app.services.embedding_providers.ollama_provider import OllamaEmbeddingProvider
from app.services.embedding_providers.openai_provider import OpenAIEmbeddingProvider
from app.services.embedding_model_registry import get_embedding_model_spec
from app.services.embedding_service import EmbeddingService
from app.schemas.ingest_request import IndexingMode, IngestMetadata
from app.services.pdf_parsers.factory import PdfParserFactory
from app.services.pdf_parsers.pymupdf_parser import PyMuPdfParser
from app.services.pdf_parsers.pypdf_parser import PyPdfParser
from app.workers.rag_ingestion_worker import _should_create_chunk_embeddings


def test_embedding_provider_factory_selects_openai():
    settings = Settings(
        EMBEDDING_PROVIDER=EmbeddingProviderName.OPENAI,
        EMBEDDING_MODEL="text-embedding-3-small",
        EMBEDDING_DIMENSION=1536,
        ALLOW_FAKE_EMBEDDINGS=True,
    )
    assert isinstance(EmbeddingProviderFactory.build(settings), OpenAIEmbeddingProvider)


def test_embedding_provider_factory_selects_ollama():
    settings = Settings(
        EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA,
        EMBEDDING_MODEL="nomic-embed-text",
        EMBEDDING_DIMENSION=768,
    )
    assert isinstance(EmbeddingProviderFactory.build(settings), OllamaEmbeddingProvider)


def test_embedding_model_registry_returns_supported_dimensions():
    assert get_embedding_model_spec(EmbeddingProviderName.OLLAMA, "embeddinggemma").dimension == 768
    assert get_embedding_model_spec(EmbeddingProviderName.OLLAMA, "nomic-embed-text").dimension == 768
    assert get_embedding_model_spec(EmbeddingProviderName.OLLAMA, "bge-m3").dimension == 1024
    assert get_embedding_model_spec(EmbeddingProviderName.OPENAI, "text-embedding-3-small").dimension == 1536


def test_embedding_dimension_is_derived_when_missing():
    settings = Settings(
        EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA,
        EMBEDDING_MODEL="bge-m3",
        EMBEDDING_DIMENSION=None,
    )

    assert settings.embedding_dimension == 1024


def test_embedding_model_registry_rejects_chat_model():
    try:
        Settings(EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA, EMBEDDING_MODEL="mistral:latest")
    except ValueError as exc:
        assert "chat/generation model" in str(exc)
    else:
        raise AssertionError("mistral:latest should not be accepted as EMBEDDING_MODEL")


def test_embedding_model_registry_rejects_other_chat_models():
    for model in ("gemma4", "llama3.1", "qwen2.5:latest"):
        try:
            Settings(EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA, EMBEDDING_MODEL=model)
        except ValueError as exc:
            assert "chat/generation model" in str(exc)
        else:
            raise AssertionError(f"{model} should not be accepted as EMBEDDING_MODEL")


def test_embedding_model_registry_rejects_dimension_mismatch():
    try:
        Settings(
            EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA,
            EMBEDDING_MODEL="nomic-embed-text",
            EMBEDDING_DIMENSION=1536,
        )
    except ValueError as exc:
        assert "Embedding dimension mismatch" in str(exc)
    else:
        raise AssertionError("nomic-embed-text must require 768 dimensions")


def test_openai_requires_key_unless_fake_embeddings_enabled(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        Settings(
            EMBEDDING_PROVIDER=EmbeddingProviderName.OPENAI,
            EMBEDDING_MODEL="text-embedding-3-small",
            EMBEDDING_DIMENSION=1536,
            ALLOW_FAKE_EMBEDDINGS=False,
        )
    except ValueError as exc:
        assert "OPENAI_API_KEY is required" in str(exc)
    else:
        raise AssertionError("OpenAI without key should fail unless fake embeddings are enabled")


def test_openai_fake_embeddings_work_only_when_enabled():
    settings = Settings(
        EMBEDDING_PROVIDER=EmbeddingProviderName.OPENAI,
        EMBEDDING_MODEL="text-embedding-3-small",
        EMBEDDING_DIMENSION=1536,
        ALLOW_FAKE_EMBEDDINGS=True,
    )
    provider = EmbeddingProviderFactory.build(settings)

    first = provider.embed_texts(["same text"])
    second = provider.embed_texts(["same text"])

    assert first == second
    assert len(first[0]) == 1536


def test_dispatcher_factory_selects_db_worker():
    settings = Settings(ASYNC_BACKEND=AsyncBackend.DB_WORKER)
    assert isinstance(JobDispatcherFactory.build(settings), DbWorkerDispatcher)


def test_auto_create_tables_defaults_false():
    settings = Settings()
    assert settings.auto_create_tables is False


def test_graph_rag_create_chunk_embeddings_defaults_false():
    settings = Settings()
    assert settings.graph_rag_create_chunk_embeddings is False


def test_ingest_metadata_indexing_mode_defaults_standard():
    metadata = IngestMetadata()
    assert metadata.indexing_mode == IndexingMode.STANDARD


def test_graph_mode_embedding_creation_is_flag_controlled():
    assert _should_create_chunk_embeddings("GRAPH", graph_rag_create_chunk_embeddings=False) is False
    assert _should_create_chunk_embeddings("GRAPH", graph_rag_create_chunk_embeddings=True) is True


def test_standard_and_both_modes_always_create_embeddings():
    assert _should_create_chunk_embeddings("STANDARD", graph_rag_create_chunk_embeddings=False) is True
    assert _should_create_chunk_embeddings("BOTH", graph_rag_create_chunk_embeddings=False) is True


def test_settings_accepts_postgresql_only_poc_config():
    settings = Settings(
        DATABASE_URL="postgresql://library_user:library_pass@localhost:5432/online_library",
    )

    assert settings.sqlalchemy_database_url.startswith("postgresql+psycopg://")


def test_pdf_parser_factory_selects_pymupdf():
    settings = Settings(PDF_PARSER="pymupdf")
    assert isinstance(PdfParserFactory.build(settings), PyMuPdfParser)


def test_pdf_parser_factory_selects_pypdf():
    settings = Settings(PDF_PARSER="pypdf")
    assert isinstance(PdfParserFactory.build(settings), PyPdfParser)


def test_ollama_embedding_provider_batches_texts(monkeypatch):
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {"embeddings": [[0.1, 0.2], [0.3, 0.4]]}

    class FakeClient:
        def __init__(self, timeout):
            self.timeout = timeout
            captured["timeout"] = timeout

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.embedding_providers.ollama_provider.httpx.Client", FakeClient)

    provider = OllamaEmbeddingProvider("http://ollama.local", "embeddinggemma", timeout_seconds=12.5)
    vectors = provider.embed_texts(["first", "second"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["timeout"] == 12.5
    assert captured["url"] == "http://ollama.local/api/embed"
    assert captured["json"] == {"model": "embeddinggemma", "input": ["first", "second"]}


def test_embedding_service_uses_configured_batch_size():
    calls = []

    class FakeProvider:
        provider_name = "fake"
        model = "fake-model"

        def embed_texts(self, texts):
            calls.append(list(texts))
            return [[float(len(text))] * 768 for text in texts]

    settings = Settings(
        EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA,
        EMBEDDING_MODEL="nomic-embed-text",
        EMBEDDING_DIMENSION=768,
        EMBEDDING_BATCH_SIZE=2,
    )
    vectors = EmbeddingService(FakeProvider(), settings).embed_chunks(["a", "bb", "ccc", "dddd", "eeeee"])

    assert calls == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
    assert [vector[0] for vector in vectors] == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert all(len(vector) == 768 for vector in vectors)


def test_embedding_service_retries_with_smaller_batches_on_failure():
    calls = []

    class FakeProvider:
        provider_name = "fake"
        model = "fake-model"

        def embed_texts(self, texts):
            calls.append(list(texts))
            if len(texts) == 4:
                raise TimeoutError("simulated ollama timeout")
            return [[float(len(text))] * 768 for text in texts]

    settings = Settings(
        EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA,
        EMBEDDING_MODEL="nomic-embed-text",
        EMBEDDING_DIMENSION=768,
        EMBEDDING_BATCH_SIZE=4,
        EMBEDDING_MAX_RETRIES=2,
        EMBEDDING_RETRY_BACKOFF_SECONDS=0,
        EMBEDDING_RETRY_SHRINK_BATCH=True,
        EMBEDDING_MIN_BATCH_SIZE=1,
    )
    profile_events = []
    vectors = EmbeddingService(FakeProvider(), settings).embed_chunks(
        ["a", "bb", "ccc", "dddd"],
        on_batch_profile=profile_events.append,
    )

    assert calls == [["a", "bb", "ccc", "dddd"], ["a", "bb"], ["ccc", "dddd"]]
    assert [vector[0] for vector in vectors] == [1.0, 2.0, 3.0, 4.0]
    assert profile_events[-1]["status"] == "RETRIED"
    assert profile_events[-1]["attempt"] == 1


def test_embedding_service_rejects_vector_count_mismatch():
    class FakeProvider:
        provider_name = "fake"
        model = "fake-model"

        def embed_texts(self, texts):
            return [[0.1] * 768]

    settings = Settings(
        EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA,
        EMBEDDING_MODEL="nomic-embed-text",
        EMBEDDING_DIMENSION=768,
    )
    try:
        EmbeddingService(FakeProvider(), settings).embed_chunks(["first", "second"])
    except ValueError as exc:
        assert "Embedding count mismatch" in str(exc)
    else:
        raise AssertionError("Embedding count mismatch should fail")


def test_embedding_service_rejects_vector_dimension_mismatch():
    class FakeProvider:
        provider_name = "fake"
        model = "fake-model"

        def embed_texts(self, texts):
            return [[0.1, 0.2] for _ in texts]

    settings = Settings(
        EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA,
        EMBEDDING_MODEL="nomic-embed-text",
        EMBEDDING_DIMENSION=768,
    )
    try:
        EmbeddingService(FakeProvider(), settings).embed_chunks(["first"])
    except ValueError as exc:
        assert "Embedding dimension mismatch" in str(exc)
    else:
        raise AssertionError("Embedding dimension mismatch should fail")
