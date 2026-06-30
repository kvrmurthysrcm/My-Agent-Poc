from collections.abc import Awaitable, Callable

from fastapi import Request, Response

from app.trace_context import trace_context_middleware


async def request_context_middleware(
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
) -> Response:
    return await trace_context_middleware(request, call_next)
