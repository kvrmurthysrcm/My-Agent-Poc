from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """Request body for JSON-based natural-language questions."""

    question: str = Field(..., min_length=1)
    limit: int = Field(10, ge=1, le=100)
    offset: int = Field(0, ge=0)
    include_raw: bool = True


class ToolChoice(BaseModel):
    """The selected MCP tool and arguments used for the tool call."""

    tool_name: str
    arguments: dict[str, Any]
    reason: str = ""
    selection_mode: str = "llm"
    fallback_used: bool = False


class AskResponse(BaseModel):
    """Response returned by the NLQ agent."""

    question: str
    selected_tool: str | None
    tool_arguments: dict[str, Any]
    answer: str
    debug: dict[str, Any]
    raw_tool_result: dict[str, Any] | None = None
