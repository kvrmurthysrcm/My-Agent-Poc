from app.core.config import Settings
from app.core.constants import AsyncBackend, EmbeddingProviderName
from app.services.async_backends.db_worker_dispatcher import DbWorkerDispatcher
from app.services.async_backends.factory import JobDispatcherFactory
from app.services.embedding_providers.factory import EmbeddingProviderFactory
from app.services.embedding_providers.ollama_provider import OllamaEmbeddingProvider
from app.services.embedding_providers.openai_provider import OpenAIEmbeddingProvider
from app.services.embedding_service import EmbeddingService
from app.services.pdf_parsers.factory import PdfParserFactory
from app.services.pdf_parsers.pymupdf_parser import PyMuPdfParser
from app.services.pdf_parsers.pypdf_parser import PyPdfParser


def test_embedding_provider_factory_selects_openai():
    settings = Settings(EMBEDDING_PROVIDER=EmbeddingProviderName.OPENAI, EMBEDDING_MODEL="text-embedding-3-small")
    assert isinstance(EmbeddingProviderFactory.build(settings), OpenAIEmbeddingProvider)


def test_embedding_provider_factory_selects_ollama():
    settings = Settings(EMBEDDING_PROVIDER=EmbeddingProviderName.OLLAMA, EMBEDDING_MODEL="mistral:latest")
    assert isinstance(EmbeddingProviderFactory.build(settings), OllamaEmbeddingProvider)


def test_dispatcher_factory_selects_db_worker():
    settings = Settings(ASYNC_BACKEND=AsyncBackend.DB_WORKER)
    assert isinstance(JobDispatcherFactory.build(settings), DbWorkerDispatcher)


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

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return None

        def post(self, url, json):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

    monkeypatch.setattr("app.services.embedding_providers.ollama_provider.httpx.Client", FakeClient)

    provider = OllamaEmbeddingProvider("http://ollama.local", "embeddinggemma")
    vectors = provider.embed_texts(["first", "second"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert captured["url"] == "http://ollama.local/api/embed"
    assert captured["json"] == {"model": "embeddinggemma", "input": ["first", "second"]}


def test_embedding_service_uses_configured_batch_size():
    calls = []

    class FakeProvider:
        provider_name = "fake"
        model = "fake-model"

        def embed_texts(self, texts):
            calls.append(list(texts))
            return [[float(len(text))] for text in texts]

    settings = Settings(EMBEDDING_BATCH_SIZE=2)
    vectors = EmbeddingService(FakeProvider(), settings).embed_chunks(["a", "bb", "ccc", "dddd", "eeeee"])

    assert calls == [["a", "bb"], ["ccc", "dddd"], ["eeeee"]]
    assert vectors == [[1.0], [2.0], [3.0], [4.0], [5.0]]
