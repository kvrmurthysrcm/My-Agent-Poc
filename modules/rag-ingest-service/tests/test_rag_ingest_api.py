import json

from fastapi.testclient import TestClient

from app.core.config import get_settings
from app.db import models  # noqa: F401
from app.db.session import Base, engine
from app.main import app


def setup_function():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def test_health_endpoint():
    with TestClient(app) as client:
        response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


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
