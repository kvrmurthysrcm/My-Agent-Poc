from __future__ import annotations

from contextvars import ContextVar
from secrets import token_hex

_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_span_id: ContextVar[str | None] = ContextVar("span_id", default=None)
_request_id: ContextVar[str | None] = ContextVar("request_id", default=None)


def outbound_trace_headers() -> dict[str, str]:
    trace_id = _trace_id.get() or token_hex(16)
    parent_span_id = _span_id.get()
    span_id = token_hex(8)
    _trace_id.set(trace_id)
    _span_id.set(span_id)
    headers = {"traceparent": f"00-{trace_id}-{span_id}-01", "X-Trace-Id": trace_id, "X-Span-Id": span_id}
    if parent_span_id:
        headers["X-Parent-Span-Id"] = parent_span_id
    request_id = _request_id.get()
    if request_id:
        headers["X-Request-ID"] = request_id
    return headers
