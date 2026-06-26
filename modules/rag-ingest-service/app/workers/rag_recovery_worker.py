import argparse
import logging
from time import sleep

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.repositories.rag_job_repository import RagJobRepository
from app.workers.rag_ingestion_worker import process_queued_jobs

logger = logging.getLogger("rag_recovery_worker")


def recover_stale_jobs_once(stale_after_seconds: int | None = None) -> int:
    settings = get_settings()
    db = SessionLocal()
    try:
        recovered = RagJobRepository(db).recover_stale_processing_jobs(
            stale_after_seconds=stale_after_seconds or settings.recovery_stale_after_seconds
        )
        db.commit()
        return recovered
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_recovery_worker(once: bool = False, process_recovered: bool = True, stale_after_seconds: int | None = None) -> None:
    settings = get_settings()
    logger.info(
        "Starting RAG recovery worker once=%s process_recovered=%s stale_after_seconds=%s poll_interval_seconds=%s",
        once,
        process_recovered,
        stale_after_seconds or settings.recovery_stale_after_seconds,
        settings.recovery_worker_poll_interval_seconds,
    )
    while True:
        recovered = recover_stale_jobs_once(stale_after_seconds=stale_after_seconds)
        processed = process_queued_jobs() if process_recovered else 0
        logger.info("RAG recovery worker recovered=%s processed=%s", recovered, processed)
        if once:
            return
        sleep(settings.recovery_worker_poll_interval_seconds)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Recover stale RAG ingestion PROCESSING jobs")
    parser.add_argument("--once", action="store_true", help="Run one recovery poll and exit")
    parser.add_argument(
        "--no-process",
        action="store_true",
        help="Only requeue stale PROCESSING jobs; do not process queued jobs in this process",
    )
    parser.add_argument("--stale-after-seconds", type=int, default=None, help="Override RECOVERY_STALE_AFTER_SECONDS")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    try:
        run_recovery_worker(
            once=args.once,
            process_recovered=not args.no_process,
            stale_after_seconds=args.stale_after_seconds,
        )
    except KeyboardInterrupt:
        logger.info("RAG recovery worker stopped")


if __name__ == "__main__":
    main()
