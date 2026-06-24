from typing import Protocol


class JobDispatcher(Protocol):
    def dispatch_ingestion_job(self, job_id: str, resource_id: str) -> None:
        ...
