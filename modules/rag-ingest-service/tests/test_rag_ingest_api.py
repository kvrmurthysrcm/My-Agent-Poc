import asyncio
import json
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient
from sqlalchemy import select
from starlette.datastructures import UploadFile

from app.core.config import get_settings
from app.db.models import RagChunkEmbedding, RagDocumentChunk, RagIngestionJob, RagProcessingError, Resource
from app.db import models  # noqa: F401
from app.db.session import Base, SessionLocal, engine
from app.main import app
from app.services.file_storage_service import FileStorageService
from app.services.chunking_types import TextChunk
from app.utils.hashing import sha256_text


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_endpoint():
    with TestClient(app) as client:
        response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_upload_ui_endpoint():
    with TestClient(app) as client:
        response = client.get("/ui")
    assert response.status_code == 200
    assert "RAG Ingestion Service" in response.text
    assert "multipart" not in response.text.lower()


def test_successful_upload_returns_resource_and_job():
    get_settings.cache_clear()
    metadata = {
        "title": "Provider Claims Submission Policy",
        "resource_type": "DOCUMENT",
        "category_name": "Claims",
        "source_system": "manual_upload",
        "tags": ["claims", "policy"],
    }
    with TestClient(app) as client:
        response = client.post(
            "/rag/ingest",
            files={"file": ("sample.txt", b"Heading:\nThis is a policy document for provider claims submission.", "text/plain")},
            data={"metadata": json.dumps(metadata)},
        )
    assert response.status_code == 202
    body = response.json()
    assert body["resource_id"]
    assert body["job_id"]
    assert body["status"] == "QUEUED"

    db = SessionLocal()
    try:
        resource = db.scalar(select(Resource).where(Resource.resource_id == body["resource_id"]))
        job = db.scalar(select(RagIngestionJob).where(RagIngestionJob.job_id == body["job_id"]))
        assert resource.ingestion_status == "READY"
        assert resource.storage_path is None
        assert resource.file_url is None
        assert job.chunking_strategy == "SEMANTIC_RECURSIVE"
        assert job.chunk_size_tokens == 1200
        assert job.chunk_overlap_tokens == 80
    finally:
        db.close()


def test_empty_extracted_text_marks_job_failed():
    with TestClient(app) as client:
        response = client.post(
            "/rag/ingest",
            files={"file": ("empty.txt", b"   \n\t", "text/plain")},
            data={"metadata": json.dumps({"title": "Empty"})},
        )

    assert response.status_code == 202
    db = SessionLocal()
    try:
        job = db.get(RagIngestionJob, response.json()["job_id"])
        resource = db.get(Resource, response.json()["resource_id"])
        error = db.scalar(select(RagProcessingError).where(RagProcessingError.job_id == job.job_id))
        assert job.status == "FAILED"
        assert resource.ingestion_status == "FAILED"
        assert "Extracted text is empty" in job.error_message
        assert error is not None
    finally:
        db.close()


def test_zero_chunks_marks_job_failed(monkeypatch):
    monkeypatch.setattr("app.workers.rag_ingestion_worker.ChunkingService.chunk", lambda *args, **kwargs: [])

    with TestClient(app) as client:
        response = client.post(
            "/rag/ingest",
            files={"file": ("zero-chunks.txt", b"Text that parser can extract.", "text/plain")},
            data={"metadata": json.dumps({"title": "Zero Chunks"})},
        )

    assert response.status_code == 202
    db = SessionLocal()
    try:
        job = db.get(RagIngestionJob, response.json()["job_id"])
        resource = db.get(Resource, response.json()["resource_id"])
        assert job.status == "FAILED"
        assert resource.ingestion_status == "FAILED"
        assert "zero chunks" in job.error_message
    finally:
        db.close()


def test_embedding_count_mismatch_marks_job_failed(monkeypatch):
    chunks = [
        TextChunk(
            chunk_index=0,
            chunk_text="First chunk text.",
            token_count=3,
            char_count=17,
            chunk_hash_sha256=sha256_text("First chunk text."),
        ),
        TextChunk(
            chunk_index=1,
            chunk_text="Second chunk text.",
            token_count=3,
            char_count=18,
            chunk_hash_sha256=sha256_text("Second chunk text."),
        ),
    ]
    monkeypatch.setattr("app.workers.rag_ingestion_worker.ChunkingService.chunk", lambda *args, **kwargs: chunks)
    monkeypatch.setattr(
        "app.workers.rag_ingestion_worker.EmbeddingService.embed_chunks",
        lambda *args, **kwargs: [[0.1] * 1536],
    )

    with TestClient(app) as client:
        response = client.post(
            "/rag/ingest",
            files={"file": ("mismatch.txt", b"Text that parser can extract for mismatch.", "text/plain")},
            data={"metadata": json.dumps({"title": "Embedding Mismatch"})},
        )

    assert response.status_code == 202
    db = SessionLocal()
    try:
        job = db.get(RagIngestionJob, response.json()["job_id"])
        resource = db.get(Resource, response.json()["resource_id"])
        error = db.scalar(select(RagProcessingError).where(RagProcessingError.job_id == job.job_id))
        assert job.status == "FAILED"
        assert resource.ingestion_status == "FAILED"
        assert "Embedding count mismatch" in job.error_message
        assert error is not None
    finally:
        db.close()


def test_ingestion_embeds_context_enriched_chunk_text(monkeypatch):
    captured_texts = []

    def capture_embed_chunks(self, texts, *args, **kwargs):
        captured_texts.extend(texts)
        return [[0.1] * self.settings.embedding_dimension for _ in texts]

    monkeypatch.setattr("app.workers.rag_ingestion_worker.EmbeddingService.embed_chunks", capture_embed_chunks)

    metadata = {
        "title": "Frankenstein",
        "author": "Mary Shelley",
        "category_name": "Scifi",
        "tags": ["classic", "gothic"],
        "description": "A gothic novel.",
    }
    with TestClient(app) as client:
        response = client.post(
            "/rag/ingest",
            files={
                "file": (
                    "frankenstein.txt",
                    b"[Page 1] Frankenstein18 Letter 1 begins with a meaningful passage about Victor and his family.",
                    "text/plain",
                )
            },
            data={"metadata": json.dumps(metadata)},
        )

    assert response.status_code == 202
    assert captured_texts
    first_input = captured_texts[0]
    assert "Title: Frankenstein" in first_input
    assert "Author: Mary Shelley" in first_input
    assert "Category: Scifi" in first_input
    assert "Tags: classic, gothic" in first_input
    assert "[Page 1]" not in first_input


def test_temp_file_paths_are_unique_when_filenames_match():
    metadata = {"title": "Duplicate Name"}
    with TestClient(app) as client:
        first = client.post(
            "/rag/ingest",
            files={"file": ("same.txt", b"First unique temp path document.", "text/plain")},
            data={"metadata": json.dumps(metadata)},
        )
        second = client.post(
            "/rag/ingest",
            files={"file": ("same.txt", b"Second unique temp path document.", "text/plain")},
            data={"metadata": json.dumps(metadata)},
        )

    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["resource_id"] != second.json()["resource_id"]


def test_file_storage_uses_unique_tmp_paths_for_same_filename(tmp_path):
    settings = get_settings().model_copy(update={"storage_root": tmp_path})
    storage = FileStorageService(settings)

    async def save_two():
        first = UploadFile(BytesIO(b"first"), filename="same.txt")
        second = UploadFile(BytesIO(b"second"), filename="same.txt")
        first_path, _, _ = await storage.save_upload(first)
        second_path, _, _ = await storage.save_upload(second)
        return first_path, second_path

    first_path, second_path = asyncio.run(save_two())

    assert first_path != second_path
    assert first_path.parent != second_path.parent
    assert first_path.parent.parent.name == "tmp"
    assert second_path.parent.parent.name == "tmp"


def test_file_storage_accepts_dots_in_filename(tmp_path):
    settings = get_settings().model_copy(update={"storage_root": tmp_path})
    storage = FileStorageService(settings)
    upload = UploadFile(BytesIO(b"content"), filename="Ramayana.of.Valmiki.by.Hari.Prasad.Shastri.pdf")

    path, size, file_hash = asyncio.run(storage.save_upload(upload))

    assert path.name == "Ramayana.of.Valmiki.by.Hari.Prasad.Shastri.pdf"
    assert path.exists()
    assert size == len(b"content")
    assert file_hash


def test_file_storage_oversized_upload_returns_validation_error_and_cleans_temp(tmp_path):
    settings = get_settings().model_copy(update={"storage_root": tmp_path, "max_upload_mb": 1})
    storage = FileStorageService(settings)
    upload = UploadFile(BytesIO(b"x" * (1024 * 1024 + 1)), filename="large.with.dots.pdf")

    try:
        asyncio.run(storage.save_upload(upload))
    except Exception as exc:
        assert "Upload exceeds maximum size" in str(exc)
    else:
        raise AssertionError("Expected oversized upload to fail")

    tmp_root = tmp_path / "tmp"
    assert not list(tmp_root.rglob("*")) if tmp_root.exists() else True


def test_invalid_file_extension_fails():
    metadata = {"title": "Bad Upload"}
    with TestClient(app) as client:
        response = client.post(
            "/rag/ingest",
            files={"file": ("sample.exe", b"bad", "application/octet-stream")},
            data={"metadata": json.dumps(metadata)},
        )
    assert response.status_code == 400


def test_invalid_metadata_fails():
    with TestClient(app) as client:
        response = client.post(
            "/rag/ingest",
            files={"file": ("sample.txt", b"hello", "text/plain")},
            data={"metadata": "{not-json"},
        )
    assert response.status_code == 400


def test_job_status_endpoint_works():
    metadata = {"title": "Status Upload"}
    with TestClient(app) as client:
        created = client.post(
            "/rag/ingest",
            files={"file": ("sample.txt", b"Simple document text for status lookup.", "text/plain")},
            data={"metadata": json.dumps(metadata)},
        )
        job_id = created.json()["job_id"]
        response = client.get(f"/rag/ingest/jobs/{job_id}")
    assert response.status_code == 200
    assert response.json()["job_id"] == job_id


def test_upload_uses_epub_metadata_when_title_omitted(tmp_path):
    epub_path = tmp_path / "book.epub"
    with ZipFile(epub_path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr(
            "META-INF/container.xml",
            """<container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
              <rootfiles>
                <rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/>
              </rootfiles>
            </container>""",
        )
        archive.writestr(
            "OEBPS/content.opf",
            """<package xmlns="http://www.idpf.org/2007/opf">
              <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
                <dc:title>File Supplied EPUB Title</dc:title>
                <dc:creator>File Supplied Author</dc:creator>
                <dc:language>en</dc:language>
              </metadata>
              <manifest><item id="c1" href="chapter.xhtml" media-type="application/xhtml+xml"/></manifest>
              <spine><itemref idref="c1"/></spine>
            </package>""",
        )
        archive.writestr("OEBPS/chapter.xhtml", "<html><body><p>Chapter text.</p></body></html>")

    with TestClient(app) as client, epub_path.open("rb") as handle:
        response = client.post(
            "/rag/ingest",
            files={"file": ("book.epub", handle, "application/epub+zip")},
            data={"metadata": json.dumps({"source_system": "metadata-test"})},
        )

    assert response.status_code == 202
    resource_id = response.json()["resource_id"]

    db = SessionLocal()
    try:
        resource = db.scalar(select(Resource).where(Resource.resource_id == resource_id))
        assert resource.title == "File Supplied EPUB Title"
        assert resource.language == "en"
    finally:
        db.close()


def test_can_keep_original_file_when_cleanup_disabled(monkeypatch):
    monkeypatch.setenv("DELETE_ORIGINAL_FILE_AFTER_INGESTION", "false")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.post(
            "/rag/ingest",
            files={"file": ("keep.txt", b"Keep this original file after ingestion.", "text/plain")},
            data={"metadata": json.dumps({"title": "Keep Original"})},
        )

    assert response.status_code == 202
    resource_id = response.json()["resource_id"]
    db = SessionLocal()
    try:
        resource = db.scalar(select(Resource).where(Resource.resource_id == resource_id))
        assert resource.ingestion_status == "READY"
        assert resource.storage_path is not None
    finally:
        db.close()
        monkeypatch.delenv("DELETE_ORIGINAL_FILE_AFTER_INGESTION", raising=False)
        get_settings.cache_clear()


def test_dev_delete_resource_removes_rag_rows():
    metadata = {"title": "Delete Me"}
    with TestClient(app) as client:
        created = client.post(
            "/rag/ingest",
            files={"file": ("delete-me.txt", b"Delete this document after ingestion.", "text/plain")},
            data={"metadata": json.dumps(metadata)},
        )
        resource_id = created.json()["resource_id"]
        response = client.delete(f"/rag/dev/resources/{resource_id}")

    assert response.status_code == 200
    body = response.json()
    assert body["deleted"] is True
    assert body["deleted_counts"]["resources"] == 1
    assert body["deleted_counts"]["rag_document_chunks"] >= 1
    assert body["deleted_counts"]["rag_chunk_embeddings"] >= 1

    db = SessionLocal()
    try:
        assert db.get(Resource, resource_id) is None
        assert db.scalar(select(RagDocumentChunk).where(RagDocumentChunk.resource_id == resource_id)) is None
        assert db.scalar(select(RagChunkEmbedding)) is None
    finally:
        db.close()


def test_dev_delete_resource_hidden_outside_local_profile(monkeypatch):
    monkeypatch.setenv("APP_PROFILE", "prod")
    get_settings.cache_clear()

    with TestClient(app) as client:
        response = client.delete("/rag/dev/resources/00000000-0000-0000-0000-000000000000")

    assert response.status_code == 404

    monkeypatch.delenv("APP_PROFILE", raising=False)
    get_settings.cache_clear()
