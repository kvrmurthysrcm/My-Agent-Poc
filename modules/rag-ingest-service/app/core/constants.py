from enum import StrEnum


class IngestionStatus(StrEnum):
    NOT_INDEXED = "NOT_INDEXED"
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"


class JobStatus(StrEnum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class AsyncBackend(StrEnum):
    FASTAPI_BACKGROUND_TASKS = "fastapi_background_tasks"
    DB_WORKER = "db_worker"
    RQ = "rq"
    KAFKA = "kafka"


class EmbeddingProviderName(StrEnum):
    OPENAI = "openai"
    OLLAMA = "ollama"


SUPPORTED_MIME_TYPES = {
    ".txt": {"text/plain", "application/octet-stream"},
    ".pdf": {"application/pdf"},
    ".docx": {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/octet-stream",
    },
}
