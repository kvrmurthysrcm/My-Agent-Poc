from __future__ import annotations

import json
import re
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
    "get_books_by_author": ("book by", "books by", "written by", "author"),
    "get_books_by_genre": ("genre", "category", "section"),
    "get_books_by_tag": ("tag", "tagged", "topic", "keyword"),
    "get_resource_detail": ("resource detail", "resource id", "details for resource"),
    "search_authors": ("find author", "search author", "author named"),
    "get_available_facets": ("available authors", "available genres", "available tags", "facets", "filters"),
    "search_users": ("search users", "find users", "user email", "approval status"),
    "search_subscriptions": ("search subscriptions", "subscription status", "subscriptions for", "tier"),
    "search_approval_requests": ("approval requests", "pending approvals", "rejected approvals"),
    "search_catalog_resources": (
        "book by",
        "books by",
        "resource by",
        "resources by",
        "title",
        "genre",
        "tag",
        "catalog",
        "search books",
        "show books",
        "find books",
    ),
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

        business_override = _business_tool_choice(question, {tool.name for tool in tools}, limit, offset)
        if business_override:
            return business_override

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
            business_override = _business_tool_choice(question, {tool.name for tool in tools}, limit, offset)
            if business_override:
                tool_name = business_override.tool_name
                arguments = business_override.arguments
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
        business_override = _business_tool_choice(question, {tool.name for tool in tools}, limit, offset)
        if business_override:
            fallback = business_override.tool_name
        return ToolChoice(
            tool_name=fallback or "",
            arguments=(
                {}
                if fallback == "list_available_tables"
                else (business_override.arguments if business_override else {"limit": limit, "offset": offset})
                if fallback
                else {}
            ),
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
        "For filtered book/resource catalog questions, prefer search_catalog_resources and pass available filters such as author, q, genre, tag, tier, limit, and offset.\n"
        "Prefer specific tools when they match: get_books_by_author, get_books_by_genre, get_books_by_tag, search_authors, search_users, search_subscriptions, search_approval_requests, get_available_facets.\n"
        "Example for 'Show books by Sri Aurobindo': "
        '{"tool_name":"get_books_by_author","arguments":{"author":"Sri Aurobindo","limit":10,"offset":0},"reason":"filter resources by author"}'
        "\n\n"
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


def _business_tool_choice(
    question: str,
    available_tool_names: set[str],
    limit: int,
    offset: int,
) -> ToolChoice | None:
    normalized = question.strip()
    if not normalized:
        return None

    resource_id = _extract_uuid(normalized)
    if resource_id and "get_resource_detail" in available_tool_names:
        return ToolChoice(
            tool_name="get_resource_detail",
            arguments={"resource_id": resource_id},
            reason="Detected a resource id detail request.",
            selection_mode="deterministic_business_rule",
            fallback_used=False,
        )

    author = _extract_after_phrase(
        normalized,
        ("books by", "book by", "resources by", "resource by", "documents by", "document by", "written by"),
    )
    if author and "get_books_by_author" in available_tool_names:
        return ToolChoice(
            tool_name="get_books_by_author",
            arguments={"author": author, "limit": limit, "offset": offset},
            reason="Detected a book/resource search by author.",
            selection_mode="deterministic_business_rule",
            fallback_used=False,
        )

    genre = _extract_after_phrase(normalized, ("genre", "category", "section"))
    if genre and "get_books_by_genre" in available_tool_names:
        return ToolChoice(
            tool_name="get_books_by_genre",
            arguments={"genre": genre, "limit": limit, "offset": offset},
            reason="Detected a book/resource search by genre.",
            selection_mode="deterministic_business_rule",
            fallback_used=False,
        )

    tag = _extract_after_phrase(normalized, ("tagged", "tag", "topic", "keyword"))
    if tag and "get_books_by_tag" in available_tool_names:
        return ToolChoice(
            tool_name="get_books_by_tag",
            arguments={"tag": tag, "limit": limit, "offset": offset},
            reason="Detected a book/resource search by tag.",
            selection_mode="deterministic_business_rule",
            fallback_used=False,
        )

    lowered = normalized.lower()
    if "get_available_facets" in available_tool_names and (
        "available authors" in lowered
        or "available genres" in lowered
        or "available tags" in lowered
        or "catalog filters" in lowered
        or "facets" in lowered
    ):
        return ToolChoice(
            tool_name="get_available_facets",
            arguments={},
            reason="Detected a catalog facet/filter lookup.",
            selection_mode="deterministic_business_rule",
            fallback_used=False,
        )

    if "search_approval_requests" in available_tool_names and ("approval" in lowered or "approvals" in lowered):
        return ToolChoice(
            tool_name="search_approval_requests",
            arguments={
                "q": _search_phrase(normalized, ("approval requests", "approvals")) or "",
                "status": _status_from_question(normalized, ("PENDING", "APPROVED", "REJECTED")) or "",
                "limit": limit,
                "offset": offset,
            },
            reason="Detected an approval request search.",
            selection_mode="deterministic_business_rule",
            fallback_used=False,
        )

    if "search_subscriptions" in available_tool_names and ("subscription" in lowered or "subscriptions" in lowered or "tier" in lowered):
        return ToolChoice(
            tool_name="search_subscriptions",
            arguments={
                "q": _search_phrase(normalized, ("subscriptions", "subscription")) or "",
                "tier": _tier_from_question(normalized) or "",
                "status": _status_from_question(normalized, ("ACTIVE", "EXPIRED", "CANCELLED", "INACTIVE")) or "",
                "limit": limit,
                "offset": offset,
            },
            reason="Detected a subscription search.",
            selection_mode="deterministic_business_rule",
            fallback_used=False,
        )

    if "search_users" in available_tool_names and re.search(r"\b(users?|members?|patrons?|accounts?)\b", lowered):
        return ToolChoice(
            tool_name="search_users",
            arguments={
                "q": _search_phrase(normalized, ("users", "user", "members", "member", "patrons", "patron", "accounts", "account")) or "",
                "status": _status_from_question(normalized, ("ACTIVE", "INACTIVE", "PENDING_APPROVAL", "REJECTED")) or "",
                "approval_status": _status_from_question(normalized, ("PENDING_APPROVAL", "APPROVED", "REJECTED")) or "",
                "limit": limit,
                "offset": offset,
            },
            reason="Detected a library user search.",
            selection_mode="deterministic_business_rule",
            fallback_used=False,
        )

    if "search_authors" in available_tool_names and re.search(r"\b(find|search|show|list)\b.*\bauthors?\b", lowered):
        return ToolChoice(
            tool_name="search_authors",
            arguments={
                "q": _search_phrase(normalized, ("authors", "author")) or "",
                "status": "ACTIVE",
                "limit": limit,
                "offset": offset,
            },
            reason="Detected an author lookup search.",
            selection_mode="deterministic_business_rule",
            fallback_used=False,
        )

    catalog_arguments = _catalog_search_arguments(question, limit, offset)
    if catalog_arguments and "search_catalog_resources" in available_tool_names:
        return ToolChoice(
            tool_name="search_catalog_resources",
            arguments=catalog_arguments,
            reason="Detected a filtered catalog resource search.",
            selection_mode="deterministic_business_rule",
            fallback_used=False,
        )

    return None


def _catalog_search_arguments(question: str, limit: int, offset: int) -> dict[str, Any] | None:
    normalized = question.strip()
    if not normalized:
        return None

    args: dict[str, Any] = {"limit": limit, "offset": offset, "status": "ACTIVE", "sort": "title"}
    author = _extract_after_phrase(
        normalized,
        (
            "books by",
            "book by",
            "resources by",
            "resource by",
            "documents by",
            "document by",
            "author",
            "written by",
        ),
    )
    title = _extract_after_phrase(
        normalized,
        (
            "title",
            "titled",
            "called",
            "named",
        ),
    )
    genre = _extract_after_phrase(normalized, ("genre", "category"))
    tag = _extract_after_phrase(normalized, ("tag", "tagged"))

    if author:
        args["author"] = author
    if title:
        args["q"] = title
    if genre:
        args["genre"] = genre
    if tag:
        args["tag"] = tag

    has_catalog_intent = bool(
        re.search(r"\b(book|books|resource|resources|document|documents|catalog|title|author|genre|tag)\b", normalized, re.IGNORECASE)
    )
    if len(args) > 4:
        return args
    if has_catalog_intent and re.search(r"\b(find|show|list|search)\b", normalized, re.IGNORECASE):
        stripped = re.sub(r"^(find|show|list|search)\s+", "", normalized, flags=re.IGNORECASE)
        stripped = re.sub(r"\b(books?|resources?|documents?|catalog)\b", "", stripped, flags=re.IGNORECASE).strip(" .:")
        if stripped:
            args["q"] = stripped
            return args
    return None


def _extract_uuid(text: str) -> str | None:
    match = re.search(
        r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b",
        text,
        re.IGNORECASE,
    )
    return match.group(0) if match else None


def _search_phrase(text: str, nouns: tuple[str, ...]) -> str | None:
    cleaned = text.strip(" .,:;\"'")
    cleaned = re.sub(r"^(find|show|list|search)\s+", "", cleaned, flags=re.IGNORECASE)
    for noun in nouns:
        cleaned = re.sub(rf"\b{re.escape(noun)}\b", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(
        r"\b(with|where|having|status|approval status|tier|plan|active|inactive|approved|rejected|pending|pending approval|free|premium|basic)\b",
        "",
        cleaned,
        flags=re.IGNORECASE,
    )
    return cleaned.strip(" .,:;\"'") or None


def _status_from_question(text: str, statuses: tuple[str, ...]) -> str | None:
    normalized = text.lower().replace("_", " ")
    for status in statuses:
        phrase = status.lower().replace("_", " ")
        if phrase in normalized:
            return status
    if "pending approval" in normalized and "PENDING_APPROVAL" in statuses:
        return "PENDING_APPROVAL"
    if "pending" in normalized and "PENDING" in statuses:
        return "PENDING"
    return None


def _tier_from_question(text: str) -> str | None:
    normalized = text.lower()
    for tier in ("FREE", "BASIC", "PREMIUM"):
        if tier.lower() in normalized:
            return tier
    return None


def _extract_after_phrase(text: str, phrases: tuple[str, ...]) -> str | None:
    for phrase in phrases:
        match = re.search(
            rf"\b{re.escape(phrase)}\b\s*[:=-]?\s+(.+?)(?:\s+\b(?:with|where|having|and|limit|offset|sort|in)\b|[?.!,;]|$)",
            text,
            re.IGNORECASE,
        )
        if match:
            value = match.group(1).strip(" .,:;\"'")
            value = re.sub(r"^(the|a|an)\s+", "", value, flags=re.IGNORECASE)
            return value or None
    return None


def _deterministic_summary(tool_name: str, tool_result: dict[str, Any]) -> str:
    count = tool_result.get("count")
    table = tool_result.get("table", tool_name)
    rows = tool_result.get("rows") if isinstance(tool_result.get("rows"), list) else None
    if rows is None:
        rows = tool_result.get("resources") if isinstance(tool_result.get("resources"), list) else []
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
