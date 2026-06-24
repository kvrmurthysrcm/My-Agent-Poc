from fastapi import BackgroundTasks

from app.workers.rag_ingestion_worker import process_job


class FastApiBackgroundTaskDispatcher:
    def __init__(self, background_tasks: BackgroundTasks):
        self.background_tasks = background_tasks

    def dispatch_ingestion_job(self, job_id: str, resource_id: str) -> None:
        self.background_tasks.add_task(process_job, job_id)
