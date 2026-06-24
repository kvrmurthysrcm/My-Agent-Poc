from pydantic import BaseModel


class IngestAcceptedResponse(BaseModel):
    resource_id: str
    job_id: str
    status: str
    message: str = "Document accepted. Ingestion will continue asynchronously."
