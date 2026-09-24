"""Tests for distributed-tracing request context behavior."""

from __future__ import annotations

import asyncio
import logging
import re
from collections.abc import Callable, Mapping
from typing import Any

import pytest
from fastapi import Request, Response

from modules.online_library import trace_context


def _request_with_headers(headers: Mapping[str, str]) -> Request:
    """Build a minimal ASGI request with deterministic headers.

    Args:
        headers: HTTP headers supplied to the constructed request.

    Returns:
        A FastAPI request suitable for middleware unit tests.
    """

    scope: dict[str, Any] = {
        "type": "http",
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": "/catalog/resources",
        "raw_path": b"/catalog/resources",
        "query_string": b"",
        "headers": [
            (name.lower().encode("latin-1"), value.encode("latin-1"))
            for name, value in headers.items()
        ],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }
    return Request(scope)


def test_extract_trace_accepts_a_valid_traceparent() -> None:
    """Extract parent identifiers from a W3C traceparent header."""

    trace_id, parent_span_id = trace_context._extract_trace(
        _request_with_headers(
            {
                "traceparent": (
                    "00-0123456789abcdef0123456789abcdef-0123456789abcdef-01"
                )
            }
        )
    )

    assert trace_id == "0123456789abcdef0123456789abcdef"
    assert parent_span_id == "0123456789abcdef"


def test_extract_trace_uses_valid_custom_trace_headers() -> None:
    """Use the legacy trace headers when a traceparent is absent."""

    trace_id, parent_span_id = trace_context._extract_trace(
        _request_with_headers(
            {
                "X-Trace-Id": "ABCDEF0123456789ABCDEF0123456789",
                "X-Span-Id": "parent-span",
            }
        )
    )

    assert trace_id == "abcdef0123456789abcdef0123456789"
    assert parent_span_id == "parent-span"


def test_extract_trace_generates_an_identifier_for_invalid_input() -> None:
    """Create a new trace when received trace headers are invalid."""

    trace_id, parent_span_id = trace_context._extract_trace(
        _request_with_headers(
            {"traceparent": "invalid", "X-Trace-Id": "also-invalid"}
        )
    )

    assert re.fullmatch(r"[0-9a-f]{32}", trace_id)
    assert parent_span_id is None


def test_trace_context_middleware_sets_headers_and_resets_context() -> None:
    """Expose trace metadata to the handler and the returned response."""

    expected_trace_id = "0123456789abcdef0123456789abcdef"
    request = _request_with_headers(
        {
            "traceparent": f"00-{expected_trace_id}-0123456789abcdef-01",
            "X-Request-ID": "request-123",
        }
    )

    async def call_next(next_request: Request) -> Response:
        """Assert the middleware context before returning a response.

        Args:
            next_request: Request enriched by the tracing middleware.

        Returns:
            A successful response for middleware completion.
        """

        assert trace_context.get_trace_id() == expected_trace_id
        assert trace_context.get_parent_span_id() == "0123456789abcdef"
        assert re.fullmatch(r"[0-9a-f]{16}", trace_context.get_span_id() or "")
        assert trace_context.get_request_id() == "request-123"
        assert next_request.state.trace_id == expected_trace_id
        return Response(content="ok", media_type="text/plain")

    response = asyncio.run(
        trace_context.trace_context_middleware(request, call_next)
    )

    assert response.status_code == 200
    assert response.headers["X-Trace-Id"] == expected_trace_id
    assert response.headers["X-Parent-Span-Id"] == "0123456789abcdef"
    assert response.headers["X-Request-ID"] == "request-123"
    assert re.fullmatch(
        rf"00-{expected_trace_id}-[0-9a-f]{{16}}-01",
        response.headers["traceparent"],
    )
    assert trace_context.get_trace_id() is None
    assert trace_context.get_span_id() is None
    assert trace_context.get_parent_span_id() is None
    assert trace_context.get_request_id() is None


def test_trace_context_middleware_propagates_handler_errors() -> None:
    """Preserve handler failures after recording the request event."""

    async def failing_call_next(_: Request) -> Response:
        """Raise the handler failure used to exercise the error path.

        Args:
            _: Request passed to the application handler.

        Raises:
            RuntimeError: Always, to emulate an application failure.
        """

        raise RuntimeError("handler failed")

    with pytest.raises(RuntimeError, match="handler failed"):
        asyncio.run(
            trace_context.trace_context_middleware(
                _request_with_headers({}),
                failing_call_next,
            )
        )


def test_install_log_record_factory_is_idempotent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Install tracing fields once and preserve default values in log records.

    Args:
        monkeypatch: Pytest helper used to isolate process-wide logging state.
    """

    factory_calls: list[Callable[..., logging.LogRecord]] = []
    base_factory = logging.getLogRecordFactory()

    def get_factory() -> Callable[..., logging.LogRecord]:
        """Return the normal record factory without changing global logging.

        Returns:
            The record factory active before this test.
        """

        return base_factory

    def set_factory(factory: Callable[..., logging.LogRecord]) -> None:
        """Capture an installed factory instead of mutating global logging.

        Args:
            factory: The record factory requested by the tracing module.
        """

        factory_calls.append(factory)

    monkeypatch.setattr(trace_context, "_factory_installed", False)
    monkeypatch.setattr(logging, "getLogRecordFactory", get_factory)
    monkeypatch.setattr(logging, "setLogRecordFactory", set_factory)

    trace_context.install_log_record_factory()
    trace_context.install_log_record_factory()

    assert len(factory_calls) == 1
    record = factory_calls[0](
        "online_library.tests",
        logging.INFO,
        __file__,
        1,
        "message",
        (),
        None,
    )
    assert getattr(record, "trace_id") == "-"
    assert getattr(record, "span_id") == "-"
    assert getattr(record, "parent_span_id") == "-"
    assert getattr(record, "request_id") == "-"
