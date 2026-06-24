class RqJobDispatcher:
    def __init__(self, redis_url: str, queue_name: str = "rag_ingestion"):
        self.redis_url = redis_url
        self.queue_name = queue_name

    def dispatch_ingestion_job(self, job_id: str, resource_id: str) -> None:
        # TODO: wire rq.Queue(connection=Redis.from_url(self.redis_url)) and enqueue process_job.
        raise NotImplementedError("RQ dispatcher adapter is present; queue wiring is intentionally left for deployment.")
