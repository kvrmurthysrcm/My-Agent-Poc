from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["ui"])


@router.get("/", response_class=HTMLResponse)
@router.get("/ui", response_class=HTMLResponse)
def gateway_ui() -> HTMLResponse:
    ui_path = Path(__file__).resolve().parents[1] / "ui" / "gateway.html"
    return HTMLResponse(ui_path.read_text(encoding="utf-8"))
