from fastapi import APIRouter, Depends, HTTPException

from app.core.config import Settings, get_settings
from app.schemas.answer_request import AnswerRequest
from app.schemas.answer_response import AnswerResponse
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
