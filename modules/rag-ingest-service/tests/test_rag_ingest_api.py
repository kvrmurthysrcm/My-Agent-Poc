import json
from zipfile import ZipFile

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Resource
from app.db import models  # noqa: F401
from app.db.session import Base, SessionLocal, engine
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
