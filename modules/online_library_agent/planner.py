from __future__ import annotations

import json
import time
from typing import Any

from .config import AgentConfig, load_config
from .llm import OllamaClient, extract_json_object
from .mcp_client import OnlineLibraryMCPClient, ToolInfo
from .models import ToolChoice


KEYWORD_TOOL_HINTS: dict[str, tuple[str, ...]] = {
    "list_available_tables": ("available tools", "available data", "what can you answer", "tables", "datasets"),
    "get_library_users": ("user", "users", "member", "members", "patron", "account", "approval status"),
    "get_resources": ("book", "books", "resource", "resources", "title", "isbn", "publisher", "content"),
    "get_authors": ("author", "authors", "writer", "writers"),
    "get_categories": ("category", "categories", "genre", "genres", "section", "classification"),
    "get_tags": ("tag", "tags", "topic", "topics", "keyword", "keywords"),
    "get_reading_progress": ("reading", "progress", "current page", "last read"),
    "get_user_bookshelf": ("bookshelf", "checkout", "checked out", "saved"),
    "get_user_subscriptions": ("user subscription", "user subscriptions", "assigned tier"),
    "get_subscription_tiers": ("subscription tier", "subscription tiers", "plans", "membership"),
    "get_subscription_rules": ("subscription rule", "rules", "entitlement", "limits"),
    "get_user_approval_requests": ("approval request", "approval requests", "pending approval", "review queue"),
    "get_resource_authors": ("resource authors", "book authors", "linked authors"),
    "get_resource_tags": ("resource tags", "book tags", "linked tags"),
}


class OnlineLibraryPlanner:
    """Coordinates tool discovery, LLM tool choice, MCP tool call, and answer generation."""

    def __init__(
        self,
        config: AgentConfig | None = None,
        mcp_client: OnlineLibraryMCPClient | None = None,
        llm_client: OllamaClient | None = None,
    ) -> None:
        self.config = config or load_config()
        self.mcp_client = mcp_client or OnlineLibraryMCPClient(self.config)
        self.llm_client = llm_client or OllamaClient(self.config)

    async def list_tools(self) -> list[ToolInfo]:
        return await self.mcp_client.list_tools()

    async def answer_question(
        self,
        question: str,
        limit: int,
        offset: int,
        include_raw: bool,
    ) -> dict[str, Any]:
        """Main NLQ flow used by both browser forms and JSON requests."""

        started_at = time.perf_counter()
        tools = await self.mcp_client.list_tools()
        tool_names = {tool.name for tool in tools}

        # For the POC, do not let the LLM choose a random library tool for
        # clearly unrelated questions such as car inventory or showroom data.
        if not _keyword_tool_choice(question, tool_names):
            answer = self._unsupported_question_answer(question, tools)
            return self._response(
                question=question,
                choice=ToolChoice(
                    tool_name="",
                    arguments={},
                    reason="No online-library keyword matched the user question.",
                    selection_mode="domain_guardrail",
                    fallback_used=True,
                ),
                answer=answer,
                raw_tool_result=None,
                include_raw=include_raw,
                timings={
                    "tool_selection_ms": 0,
                    "mcp_tool_call_ms": 0,
                    "answer_generation_ms": 0,
                    "total_ms": _elapsed_ms(started_at),
                },
            )

        selection_started = time.perf_counter()
        choice = await self._choose_tool(question, tools, limit, offset)
        selection_ms = _elapsed_ms(selection_started)

        if choice.tool_name not in tool_names:
            answer = self._unsupported_question_answer(question, tools)
            return self._response(
                question=question,
                choice=ToolChoice(
                    tool_name="",
                    arguments={},
                    reason="No matching Online Library MCP tool was found.",
                    selection_mode=choice.selection_mode,
                    fallback_used=choice.fallback_used,
                ),
                answer=answer,
                raw_tool_result=None,
                include_raw=include_raw,
                timings={
                    "tool_selection_ms": selection_ms,
                    "mcp_tool_call_ms": 0,
                    "answer_generation_ms": 0,
                    "total_ms": _elapsed_ms(started_at),
                },
            )

        tool_started = time.perf_counter()
        tool_result = await self.mcp_client.call_tool(choice.tool_name, choice.arguments)
        tool_ms = _elapsed_ms(tool_started)

        answer_started = time.perf_counter()
        answer = await self._summarize_result(question, choice, tool_result)
        answer_ms = _elapsed_ms(answer_started)

        return self._response(
            question=question,
            choice=choice,
            answer=answer,
            raw_tool_result=tool_result,
            include_raw=include_raw,
            timings={
                "tool_selection_ms": selection_ms,
                "mcp_tool_call_ms": tool_ms,
                "answer_generation_ms": answer_ms,
                "total_ms": _elapsed_ms(started_at),
            },
        )

    async def _choose_tool(self, question: str, tools: list[ToolInfo], limit: int, offset: int) -> ToolChoice:
        """Ask the LLM to pick a tool; fallback to keyword matching if JSON is bad."""

        prompt = _tool_selection_prompt(question, tools, limit, offset)
        try:
            llm_text = await self.llm_client.generate(
                prompt,
                self.config.tool_selection_temperature,
                self.config.tool_selection_num_predict,
            )
            parsed = extract_json_object(llm_text)
        except Exception:
            parsed = None

        if parsed:
            tool_name = str(parsed.get("tool_name", "")).strip()
            arguments = parsed.get("arguments") if isinstance(parsed.get("arguments"), dict) else {}
            if tool_name == "list_available_tables":
                arguments = {}
            else:
                arguments["limit"] = _clamp_int(arguments.get("limit", limit), 1, 100)
                arguments["offset"] = max(0, _clamp_int(arguments.get("offset", offset), 0, 100000))
            return ToolChoice(
                tool_name=tool_name,
                arguments=arguments,
                reason=str(parsed.get("reason", "")),
                selection_mode="llm",
                fallback_used=False,
            )

        fallback = _keyword_tool_choice(question, {tool.name for tool in tools})
        return ToolChoice(
            tool_name=fallback or "",
            arguments={} if fallback == "list_available_tables" else ({"limit": limit, "offset": offset} if fallback else {}),
            reason="Selected by deterministic keyword fallback.",
            selection_mode="keyword_fallback",
            fallback_used=True,
        )

    async def _summarize_result(self, question: str, choice: ToolChoice, tool_result: dict[str, Any]) -> str:
        """Use the local LLM to turn raw tool JSON into a short answer."""

        prompt = _answer_prompt(question, choice, tool_result)
        try:
            answer = await self.llm_client.generate(
                prompt,
                self.config.answer_temperature,
                self.config.answer_num_predict,
            )
        except Exception:
            answer = ""
        return answer or _deterministic_summary(choice.tool_name, tool_result)

    def _response(
        self,
        question: str,
        choice: ToolChoice,
        answer: str,
        raw_tool_result: dict[str, Any] | None,
        include_raw: bool,
        timings: dict[str, int],
    ) -> dict[str, Any]:
        """Build the response with POC debug details exposed."""

        return {
            "question": question,
            "selected_tool": choice.tool_name or None,
            "tool_arguments": choice.arguments,
            "answer": answer,
            "result_type": "unsupported_question" if not choice.tool_name else "tool_result",
            "debug": {
                "llm_provider": "ollama",
                "llm_model": self.config.ollama_model,
                "ollama_base_url": self.config.ollama_base_url,
                "mcp_url": self.config.mcp_url,
                "tool_selection_temperature": self.config.tool_selection_temperature,
                "answer_temperature": self.config.answer_temperature,
                "tool_selection_num_predict": self.config.tool_selection_num_predict,
                "answer_num_predict": self.config.answer_num_predict,
                "tool_selection_mode": choice.selection_mode,
                "fallback_used": choice.fallback_used,
                "tool_selection_reason": choice.reason,
                **timings,
            },
            "raw_tool_result": raw_tool_result if include_raw else None,
        }

    def _unsupported_question_answer(self, question: str, tools: list[ToolInfo]) -> str:
        return (
            "This question does not match the online library data I can query right now. "
            "Try asking about library users, books and resources, authors, categories, tags, "
            "reading progress, subscriptions, bookshelf records, or approval requests."
        )


def _tool_selection_prompt(question: str, tools: list[ToolInfo], limit: int, offset: int) -> str:
    catalog = [
        {"name": tool.name, "description": tool.description}
        for tool in tools
    ]
    return (
        "You select one MCP tool for an online library question.\n"
        "Choose exactly one tool from the provided tools.\n"
        "If no tool matches the user's question, return an empty tool_name.\n"
        "Return only valid JSON. Do not include markdown.\n\n"
        f"User question: {question}\n"
        f"Default limit: {limit}\n"
        f"Default offset: {offset}\n\n"
        f"Tools:\n{json.dumps(catalog, indent=2)}\n\n"
        "Return this JSON shape:\n"
        '{"tool_name":"get_resources","arguments":{"limit":10,"offset":0},"reason":"short reason"}'
    )


def _answer_prompt(question: str, choice: ToolChoice, tool_result: dict[str, Any]) -> str:
    return (
        "You answer online library questions using only the supplied MCP tool result.\n"
        "Do not invent data. If rows are empty, say no rows were returned.\n"
        "The browser UI displays the returned rows in a table before your answer.\n"
        "Do not repeat every field from every row.\n"
        "Write only a short conclusion, observation, or summary that should appear after the table.\n"
        "For example: These users have an active status and their accounts were not rejected.\n"
        "Keep the answer concise and useful for a developer POC.\n\n"
        f"User question: {question}\n"
        f"Tool used: {choice.tool_name}\n"
        f"Tool arguments: {json.dumps(choice.arguments)}\n"
        f"Tool result JSON:\n{json.dumps(tool_result, indent=2)}\n"
    )


def _keyword_tool_choice(question: str, available_tool_names: set[str]) -> str | None:
    normalized = question.lower()
    best_tool = None
    best_score = 0
    for tool_name, hints in KEYWORD_TOOL_HINTS.items():
        if tool_name not in available_tool_names:
            continue
        score = sum(1 for hint in hints if hint in normalized)
        if score > best_score:
            best_tool = tool_name
            best_score = score
    return best_tool


def _deterministic_summary(tool_name: str, tool_result: dict[str, Any]) -> str:
    count = tool_result.get("count")
    table = tool_result.get("table", tool_name)
    rows = tool_result.get("rows") if isinstance(tool_result.get("rows"), list) else []
    if count == 0 or not rows:
        return f"The tool `{tool_name}` returned no rows from `{table}`."
    return f"The tool `{tool_name}` returned {count} row(s) from `{table}`."


def _clamp_int(value: Any, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        number = minimum
    return min(max(number, minimum), maximum)


def _elapsed_ms(started_at: float) -> int:
    return round((time.perf_counter() - started_at) * 1000)
