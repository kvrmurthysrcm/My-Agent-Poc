class KafkaJobDispatcher:
    def __init__(self, bootstrap_servers: str, topic: str):
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic

    def dispatch_ingestion_job(self, job_id: str, resource_id: str) -> None:
        # TODO: wire a Kafka producer and publish a rag document ingestion requested event.
        raise NotImplementedError("Kafka dispatcher adapter is present; producer wiring is intentionally left for deployment.")
