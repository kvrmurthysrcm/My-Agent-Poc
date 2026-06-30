from __future__ import annotations

import logging
import re
import time
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from secrets import token_hex
from uuid import uuid4

from fastapi import Request, Response

TRACEPARENT_PATTERN = re.compile(r"^00-([0-9a-f]{32})-([0-9a-f]{16})-([0-9a-f]{2})$")

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_span_id: ContextVar[str | None] = ContextVar("span_id", default=None)
_parent_span_id: ContextVar[str | None] = ContextVar("parent_span_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)
_factory_installed = False


def install_log_record_factory() -> None:
    global _factory_installed
    if _factory_installed:
        return
    previous_factory = logging.getLogRecordFactory()

    def record_factory(*args, **kwargs):
        record = previous_factory(*args, **kwargs)
        record.trace_id = get_trace_id() or "-"
        record.span_id = get_span_id() or "-"
        record.parent_span_id = get_parent_span_id() or "-"
        record.request_id = get_request_id() or "-"
        return record

    logging.setLogRecordFactory(record_factory)
    _factory_installed = True


def get_trace_id() -> str | None:
    return _trace_id.get()


def get_span_id() -> str | None:
    return _span_id.get()


def get_parent_span_id() -> str | None:
    return _parent_span_id.get()


def get_request_id() -> str | None:
    return _request_id.get()


async def trace_context_middleware(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
    trace_id, parent_span_id = _extract_trace(request)
    span_id = token_hex(8)
    request_id = request.headers.get("X-Request-ID") or str(uuid4())
    trace_token = _trace_id.set(trace_id)
    span_token = _span_id.set(span_id)
    parent_token = _parent_span_id.set(parent_span_id)
    request_token = _request_id.set(request_id)
    request.state.trace_id = trace_id
    request.state.span_id = span_id
    request.state.parent_span_id = parent_span_id
    request.state.request_id = request_id
    started_at = time.perf_counter()
    try:
        response = await call_next(request)
    finally:
        logging.getLogger(__name__).info(
            "request_completed",
            extra={"method": request.method, "path": request.url.path, "duration_ms": round((time.perf_counter() - started_at) * 1000, 2)},
        )
    response.headers["traceparent"] = f"00-{trace_id}-{span_id}-01"
    response.headers["X-Trace-Id"] = trace_id
    response.headers["X-Span-Id"] = span_id
    if parent_span_id:
        response.headers["X-Parent-Span-Id"] = parent_span_id
    response.headers["X-Request-ID"] = request_id
    _trace_id.reset(trace_token)
    _span_id.reset(span_token)
    _parent_span_id.reset(parent_token)
    _request_id.reset(request_token)
    return response


def _extract_trace(request: Request) -> tuple[str, str | None]:
    match = TRACEPARENT_PATTERN.match(request.headers.get("traceparent", "").strip().lower())
    if match:
        return match.group(1), match.group(2)
    trace_id = request.headers.get("X-Trace-Id", "").strip().lower()
    if re.fullmatch(r"[0-9a-f]{32}", trace_id):
        return trace_id, request.headers.get("X-Span-Id")
    return token_hex(16), None
