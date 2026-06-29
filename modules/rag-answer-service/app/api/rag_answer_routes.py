import json

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from app.core.config import Settings, get_settings
from app.schemas.answer_request import AnswerRequest
from app.schemas.answer_response import AnswerComparisonResponse, AnswerResponse
from app.services.answer_service import AnswerService

router = APIRouter(prefix="/rag", tags=["rag-answer"])


@router.post("/answer", response_model=AnswerResponse)
def answer_question(
    request: AnswerRequest,
    settings: Settings = Depends(get_settings),
) -> AnswerResponse:
    try:
        return AnswerService(settings).answer(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Answer generation failed: {type(exc).__name__}: {exc}") from exc


@router.post("/answer/compare", response_model=AnswerComparisonResponse)
def compare_answers(
    request: AnswerRequest,
    settings: Settings = Depends(get_settings),
) -> AnswerComparisonResponse:
    try:
        return AnswerService(settings).compare(request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Answer comparison failed: {type(exc).__name__}: {exc}") from exc


@router.post("/answer/compare/stream")
def stream_compare_answers(
    request: AnswerRequest,
    settings: Settings = Depends(get_settings),
) -> StreamingResponse:
    def generate():
        try:
            for event in AnswerService(settings).compare_stream(request):
                yield _sse_event(event)
        except Exception as exc:
            yield _sse_event(
                {
                    "event": "error",
                    "error_type": type(exc).__name__,
                    "message": str(exc),
                }
            )

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


def _sse_event(event: dict) -> str:
    event_name = str(event.get("event") or "message")
    return f"event: {event_name}\ndata: {json.dumps(event, ensure_ascii=False)}\n\n"
