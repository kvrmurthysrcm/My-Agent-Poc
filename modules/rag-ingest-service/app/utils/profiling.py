from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
import logging

_PROFILE_EVENTS: dict[str, list[dict]] = {}


def get_profile_events(job_id: str) -> list[dict]:
    events = []
    for event in _PROFILE_EVENTS.get(job_id, []):
        public_event = {key: value for key, value in event.items() if not key.startswith("_")}
        if public_event.get("status") == "IN_PROGRESS":
            public_event["elapsed_ms"] = round((perf_counter() - event["_started_at"]) * 1000, 2)
        events.append(public_event)
    return events


def clear_profile_events(job_id: str) -> None:
    _PROFILE_EVENTS.pop(job_id, None)


def record_profile_event(
    enabled: bool,
    logger: logging.Logger,
    job_id: str,
    resource_id: str,
    step: str,
    status: str,
    elapsed_ms: float,
    **details,
) -> None:
    if not enabled:
        return
    event = {
        "step": step,
        "status": status,
        "elapsed_ms": round(elapsed_ms, 2),
        "details": {key: value for key, value in details.items() if value is not None},
    }
    _PROFILE_EVENTS.setdefault(job_id, []).append(event)
    detail_text = " ".join(f"{key}={value}" for key, value in event["details"].items())
    logger.info(
        "PROFILE job_id=%s resource_id=%s step=%s status=%s elapsed_ms=%.2f %s",
        job_id,
        resource_id,
        step,
        status,
        elapsed_ms,
        detail_text,
    )


@contextmanager
def profile_step(
    enabled: bool,
    logger: logging.Logger,
    job_id: str,
    resource_id: str,
    step: str,
    **details,
) -> Iterator[None]:
    started = perf_counter()
    event = None
    if enabled:
        event = {
            "step": step,
            "status": "IN_PROGRESS",
            "elapsed_ms": 0.0,
            "details": {key: value for key, value in details.items() if value is not None},
            "_started_at": started,
        }
        _PROFILE_EVENTS.setdefault(job_id, []).append(event)
    try:
        yield
    except Exception:
        if enabled and event is not None:
            elapsed_ms = (perf_counter() - started) * 1000
            event["status"] = "FAILED"
            event["elapsed_ms"] = round(elapsed_ms, 2)
            event.pop("_started_at", None)
        raise
    finally:
        if enabled and event is not None and event["status"] == "IN_PROGRESS":
            elapsed_ms = (perf_counter() - started) * 1000
            event["status"] = "DONE"
            event["elapsed_ms"] = round(elapsed_ms, 2)
            event.pop("_started_at", None)
            detail_text = " ".join(f"{key}={value}" for key, value in details.items() if value is not None)
            logger.info(
                "PROFILE job_id=%s resource_id=%s step=%s elapsed_ms=%.2f %s",
                job_id,
                resource_id,
                step,
                elapsed_ms,
                detail_text,
            )
