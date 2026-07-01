from fastapi.testclient import TestClient

from app.db import models  # noqa: F401
from app.db.models import RagChunkEmbedding, RagDocumentChunk, RagIngestionJob, Resource
from app.db.session import Base, SessionLocal, engine
from app.main import app


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_admin_resources_ui_endpoint():
    with TestClient(app) as client:
        response = client.get("/ui/admin/resources")

    assert response.status_code == 200
    assert "RAG Resource Admin" in response.text


def test_admin_resource_list_includes_counts():
    resource_id = "00000000-0000-0000-0000-000000000101"
    job_id = "00000000-0000-0000-0000-000000000102"
    chunk_id = "00000000-0000-0000-0000-000000000103"
    embedding_id = "00000000-0000-0000-0000-000000000104"
    db = SessionLocal()
    try:
        resource = Resource(
            resource_id=resource_id,
            title="Frankenstein",
            rag_enabled=True,
            ingestion_status="READY",
            resource_metadata={"author": "Mary Shelley", "category_name": "Scifi", "tags": ["classic"]},
        )
        db.add(resource)
        db.add(RagIngestionJob(job_id=job_id, resource_id=resource.resource_id, status="COMPLETED", async_backend="test"))
        db.flush()
        chunk = RagDocumentChunk(
            chunk_id=chunk_id,
            resource_id=resource.resource_id,
            job_id=job_id,
            chunk_index=0,
            chunk_text="Frankenstein by Mary Shelley.",
            chunk_hash_sha256="hash",
            token_count=4,
            char_count=28,
        )
        db.add(chunk)
        db.flush()
        db.add(
            RagChunkEmbedding(
                embedding_id=embedding_id,
                chunk_id=chunk.chunk_id,
                embedding_provider="openai",
                embedding_model="text-embedding-3-small",
                embedding_version="v1",
                embedding_dimension=1536,
                vector=[0.1] * 1536,
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.get("/rag/admin/resources")

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    item = body["resources"][0]
    assert item["title"] == "Frankenstein"
    assert item["author"] == "Mary Shelley"
    assert item["category"] == "Scifi"
    assert item["chunk_count"] == 1
    assert item["embedding_count"] == 1
    assert item["job_count"] == 1


def test_admin_bulk_delete_removes_selected_resource_rows():
    resource_id = "00000000-0000-0000-0000-000000000201"
    job_id = "00000000-0000-0000-0000-000000000202"
    chunk_id = "00000000-0000-0000-0000-000000000203"
    embedding_id = "00000000-0000-0000-0000-000000000204"
    db = SessionLocal()
    try:
        resource = Resource(resource_id=resource_id, title="Delete Me", rag_enabled=True, ingestion_status="READY")
        db.add(resource)
        db.add(RagIngestionJob(job_id=job_id, resource_id=resource.resource_id, status="COMPLETED", async_backend="test"))
        db.flush()
        chunk = RagDocumentChunk(
            chunk_id=chunk_id,
            resource_id=resource.resource_id,
            job_id=job_id,
            chunk_index=0,
            chunk_text="Delete text.",
            chunk_hash_sha256="delete-hash",
            token_count=2,
            char_count=12,
        )
        db.add(chunk)
        db.flush()
        db.add(
            RagChunkEmbedding(
                embedding_id=embedding_id,
                chunk_id=chunk.chunk_id,
                embedding_provider="openai",
                embedding_model="text-embedding-3-small",
                embedding_version="v1",
                embedding_dimension=1536,
                vector=[0.1] * 1536,
            )
        )
        db.commit()
    finally:
        db.close()

    with TestClient(app) as client:
        response = client.post("/rag/admin/resources/delete", json={"resource_ids": [resource_id]})

    assert response.status_code == 200
    body = response.json()
    assert body["requested"] == 1
    assert body["deleted"] == 1
    assert body["results"][0]["deleted_counts"]["resources"] == 1
    assert body["results"][0]["deleted_counts"]["rag_document_chunks"] == 1
    assert body["results"][0]["deleted_counts"]["rag_chunk_embeddings"] == 1

    db = SessionLocal()
    try:
        assert db.get(Resource, resource_id) is None
        assert db.get(RagDocumentChunk, chunk_id) is None
        assert db.get(RagChunkEmbedding, embedding_id) is None
    finally:
        db.close()
