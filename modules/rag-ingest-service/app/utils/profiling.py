from collections.abc import Iterator
from contextlib import contextmanager
from time import perf_counter
import logging

_PROFILE_EVENTS: dict[str, list[dict]] = {}


def get_profile_events(job_id: str) -> list[dict]:
    return list(_PROFILE_EVENTS.get(job_id, []))


def clear_profile_events(job_id: str) -> None:
    _PROFILE_EVENTS.pop(job_id, None)


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
    try:
        yield
    finally:
        if enabled:
            elapsed_ms = (perf_counter() - started) * 1000
            event = {
                "step": step,
                "elapsed_ms": round(elapsed_ms, 2),
                "details": {key: value for key, value in details.items() if value is not None},
            }
            _PROFILE_EVENTS.setdefault(job_id, []).append(event)
            detail_text = " ".join(f"{key}={value}" for key, value in details.items() if value is not None)
            logger.info(
                "PROFILE job_id=%s resource_id=%s step=%s elapsed_ms=%.2f %s",
                job_id,
                resource_id,
                step,
                elapsed_ms,
                detail_text,
            )
