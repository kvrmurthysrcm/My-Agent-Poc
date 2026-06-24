from fastapi import BackgroundTasks

from app.core.config import Settings
from app.core.constants import AsyncBackend
from app.core.exceptions import UnsupportedAsyncBackendError
from app.services.async_backends.base import JobDispatcher
from app.services.async_backends.db_worker_dispatcher import DbWorkerDispatcher
from app.services.async_backends.fastapi_async_dispatcher import FastApiBackgroundTaskDispatcher
from app.services.async_backends.kafka_dispatcher import KafkaJobDispatcher
from app.services.async_backends.rq_dispatcher import RqJobDispatcher


class JobDispatcherFactory:
    @staticmethod
    def build(settings: Settings, background_tasks: BackgroundTasks | None = None) -> JobDispatcher:
        if settings.async_backend == AsyncBackend.FASTAPI_BACKGROUND_TASKS:
            if background_tasks is None:
                raise UnsupportedAsyncBackendError("FastAPI background task dispatcher requires BackgroundTasks")
            return FastApiBackgroundTaskDispatcher(background_tasks)
        if settings.async_backend == AsyncBackend.DB_WORKER:
            return DbWorkerDispatcher()
        if settings.async_backend == AsyncBackend.RQ:
            return RqJobDispatcher(redis_url=settings.rq_redis_url)
        if settings.async_backend == AsyncBackend.KAFKA:
            return KafkaJobDispatcher(settings.kafka_bootstrap_servers, settings.kafka_ingestion_topic)
        raise UnsupportedAsyncBackendError(f"Unsupported async backend: {settings.async_backend}")
