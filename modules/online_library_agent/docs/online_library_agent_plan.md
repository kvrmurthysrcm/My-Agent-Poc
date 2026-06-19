# Online Library NLQ Agent Plan

## Status

Approved and implemented.

## Module Name

Use:

```text
modules/online_library_agent/
```

Reason:

- Lowercase Python package naming.
- Clear separation from:
  - `modules/online_library`: REST API over PostgreSQL.
  - `modules/online_library_mcp`: MCP server and tools.
  - `modules/online_library_agent`: natural-language agent that uses MCP tools.

## Goal

Create a FastAPI-based agent service that accepts natural-language questions about the Online Library system.

The agent will:

1. Receive a natural-language query from a user.
2. Connect to the Online Library MCP server.
3. Call `tools/list` to discover available tools and descriptions.
4. Use local Ollama with `mistral:latest` to select the best matching MCP tool.
5. Call that MCP tool with arguments such as `limit` and `offset`.
6. Return a user-readable answer with the raw tool result included for transparency.

## Target Architecture

```text
User / Browser / API Client
        |
        | HTTP JSON
        v
online_library_agent FastAPI service
        |
        | Ollama HTTP API
        v
local Ollama mistral:latest
        |
        | MCP Streamable HTTP
        v
online_library_mcp server
        |
        | HTTP JSON
        v
online_library FastAPI API
        |
        | SQL SELECT
        v
PostgreSQL online_library DB
```

## Runtime Dependencies

Already present or planned:

- `fastapi`
- `uvicorn`
- `httpx`
- `mcp`
- `python-dotenv`

The agent should not connect directly to PostgreSQL. It should use the MCP server only.

## Required Running Services

The full local flow needs three services running:

### 1. Online Library REST API

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.online_library.api:app --reload --port 8003
```

Base URL:

```text
http://127.0.0.1:8003
```

### 2. Online Library MCP Server

```powershell
.\.venv\Scripts\python.exe -m modules.online_library_mcp.server
```

MCP URL:

```text
http://127.0.0.1:8004/mcp
```

### 3. Ollama

Ollama should have `mistral:latest` available:

```powershell
ollama pull mistral:latest
```

Ollama base URL:

```text
http://127.0.0.1:11434
```

## Configuration

Create module-local `.env` support:

```text
modules/online_library_agent/.env
```

Proposed values:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=mistral:latest
ONLINE_LIBRARY_MCP_URL=http://127.0.0.1:8004/mcp
ONLINE_LIBRARY_AGENT_HOST=127.0.0.1
ONLINE_LIBRARY_AGENT_PORT=8005
ONLINE_LIBRARY_AGENT_TIMEOUT_SECONDS=30
ONLINE_LIBRARY_AGENT_DEFAULT_LIMIT=10
```

Use `load_dotenv(..., override=True)`, same as the weather AI module, so the module-local `.env` is respected during local testing.

## Proposed Folder Structure

```text
modules/online_library_agent/
  __init__.py
  api.py
  config.py
  llm.py
  mcp_client.py
  models.py
  planner.py
  Readme.md
  .env.example
  docs/
    online_library_agent_plan.md
```

## FastAPI Endpoints

### Health

```text
GET /health
```

Returns:

- agent status
- configured MCP URL
- configured Ollama model

### Tools Discovery

```text
GET /tools
```

Purpose:

- Connect to the MCP server.
- Run `tools/list`.
- Return tool names, descriptions, and input schemas.

This is useful for debugging whether the agent can see MCP tools.

### Guided Ask Page

```text
GET /ask
```

Purpose:

- Show a simple browser page for POC demos.
- Give users guided question options that are likely to produce good results.
- Also provide one open-ended question field.

This page should not be a blank chatbot only. For this POC, guided options are better because they quickly prove the MCP + tools flow works.

Recommended layout:

1. User/account questions section.
2. Reading progress section.
3. Library content section.
4. Subscription section.
5. Open-ended NLQ section.

Each section should have:

- A dropdown of sample questions.
- A submit button.
- Optionally `limit` and `offset` fields.

The open-ended section should have:

- One text field.
- Submit button.
- Short helper text that says the assistant can answer online-library questions, not unrelated domains.

Example guided questions:

```text
List library users.
Show pending user approval requests.
Show user bookshelf records.
Show user subscription records.
Show reading progress records.
List available books and resources.
List authors.
List categories.
List tags.
Show subscription tiers.
Show subscription rules.
```

### NLQ Ask API

```text
POST /ask
```

Request:

```json
{
  "question": "List library users",
  "limit": 10,
  "offset": 0,
  "include_raw": true
}
```

Response:

```json
{
  "question": "List library users",
  "selected_tool": "get_library_users",
  "tool_arguments": {
    "limit": 10,
    "offset": 0
  },
  "answer": "The library currently has these users...",
  "debug": {
    "llm_provider": "ollama",
    "llm_model": "mistral:latest",
    "ollama_base_url": "http://127.0.0.1:11434",
    "mcp_url": "http://127.0.0.1:8004/mcp",
    "tool_selection_temperature": 0.1,
    "answer_temperature": 0.2,
    "tool_selection_mode": "llm",
    "fallback_used": false
  },
  "raw_tool_result": {
    "table": "library_users",
    "count": 3,
    "rows": []
  }
}
```

`GET /ask` and `POST /ask` can share the same processing function internally. The difference is only the response format:

- Browser form submit returns rendered HTML.
- JSON API call returns JSON.

For the POC, both the browser result and JSON response should include developer diagnostics. These details help verify how the agent made its decision. They may be hidden or removed in a real application.

Recommended diagnostics:

- selected MCP tool name
- MCP tool arguments
- LLM provider
- LLM model
- Ollama base URL
- MCP server URL
- tool-selection temperature
- answer-formatting temperature
- whether the tool was selected by LLM or fallback keyword matching
- whether fallback was used
- optional timing values for LLM selection, MCP call, and answer generation

## POC UX Recommendation

For this POC, the best user experience is a guided NLQ page rather than an empty chat box.

Recommended first screen:

```text
Online Library Agent

[User Questions]
Dropdown: List library users / Show approvals / Show subscriptions
[Ask]

[Reading Progress]
Dropdown: Show reading progress / Show bookshelf records
[Ask]

[Library Content]
Dropdown: List resources / List authors / List categories / List tags
[Ask]

[Subscription]
Dropdown: Show subscription tiers / Show subscription rules
[Ask]

[Ask Anything About The Online Library]
Text input: "List active users"
[Ask]
```

Why this is better:

- It shows useful results quickly.
- It guides users toward questions the available MCP tools can answer.
- It still allows open-ended NLQ.
- It avoids the first impression problem where a user asks unrelated questions such as "how many cars are in the showroom".

For unrelated questions, the agent should answer clearly:

```text
I can answer questions about the online library data exposed by the MCP tools. I do not have a tool for showroom or car inventory data.
```

## Request Flow

Detailed control flow for `GET /ask` form submissions and `POST /ask`:

1. Validate request body.
2. Connect to MCP server using Streamable HTTP.
3. Initialize MCP session.
4. Call `tools/list`.
5. Build a compact tool catalog from:
   - tool name
   - description
   - input schema
6. Send the user question and tool catalog to `mistral:latest`.
7. Ask the LLM to return strict JSON:

```json
{
  "tool_name": "get_library_users",
  "arguments": {
    "limit": 10,
    "offset": 0
  },
  "reason": "The user asked to list users."
}
```

8. Validate that the selected tool exists in the MCP tool list.
9. Clamp `limit` to the MCP-supported range.
10. Call the selected MCP tool.
11. Send the user question, selected tool, and tool result back to `mistral:latest`.
12. Ask the LLM to generate a concise human-readable answer.
13. Return the answer and optional raw tool result.

## Tool Selection Prompt Strategy

Use two LLM calls for clarity:

### Call 1: Tool Selection

Purpose:

- Choose one MCP tool.
- Return strict JSON only.

Prompt should include:

- User question.
- Available MCP tools and descriptions.
- JSON output contract.
- Rule: choose only from available tools.
- Rule: do not invent tool names.

Example instruction:

```text
You are selecting one MCP tool for an online library question.
Choose exactly one tool from the provided tool list.
Return only valid JSON.
Do not explain outside JSON.
```

### Call 2: Answer Formatting

Purpose:

- Convert the raw MCP result into a short user-facing answer.

Prompt should include:

- Original user question.
- Selected tool name.
- Raw tool result.
- Rule: do not invent data.
- Rule: say when the result is empty.

## Why Use Two LLM Calls?

Two calls are easier to debug for this POC:

- One call chooses the tool.
- One call summarizes the result.

This makes it clear whether a failure is caused by bad tool selection or bad answer formatting.

Later, this can be optimized into one model call if needed.

## Deterministic Fallback And Guardrails

If the LLM cannot produce valid tool-selection JSON:

1. Try a simple deterministic keyword match over MCP tool names and descriptions.
2. Example:
   - `users`, `members`, `patrons` -> `get_library_users`
   - `books`, `resources`, `titles` -> `get_resources`
   - `authors`, `writers` -> `get_authors`
   - `categories`, `genres` -> `get_categories`
   - `tags`, `topics`, `keywords` -> `get_tags`
3. If no match is found, return a clear error with the available tools.

This keeps the demo usable even when a local model returns imperfect JSON.

Also add a simple domain guardrail before tool execution:

- If the question cannot be matched to any online-library tool, do not call a random tool.
- Return a helpful message that the agent only supports online-library questions.
- Include examples of supported questions.

This handles unrelated questions such as:

```text
How many cars are there in the showroom?
```

Expected response:

```text
I do not have a tool for showroom or car inventory data. I can help with online library users, resources, authors, categories, tags, reading progress, subscriptions, and approvals.
```

## MCP Client Design

Use the official MCP Python SDK:

```python
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
```

The client helper should expose:

```python
async def list_tools() -> list[ToolInfo]
async def call_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]
```

It should open and close an MCP session per API request for the first version.

Later optimization:

- Reuse sessions if needed.
- Add pooling only after the simple path is stable.

## Ollama Client Design

Use `httpx` to call Ollama directly.

Endpoint:

```text
POST /api/generate
```

Request shape:

```json
{
  "model": "mistral:latest",
  "prompt": "...",
  "stream": false,
  "options": {
    "temperature": 0.1
  }
}
```

Keep `temperature` low for tool selection.

Recommended values:

- Tool selection temperature: `0.0` or `0.1`
- Answer formatting temperature: `0.2`

## Data Safety Notes

There is currently no auth on:

- Online Library API.
- Online Library MCP server.
- Proposed Online Library Agent.

This is acceptable for the local POC, but not production-safe.

The agent may return user/member data if asked because user-related MCP tools are intentionally enabled.

Later production requirements:

- Add auth.
- Add tool allowlists.
- Add user-data masking.
- Add audit logs for tool calls.
- Add rate limits.
- Add policy checks before user-related tools are called.

## Comments In Code

Implementation should include comments explaining:

- How `.env` is loaded.
- Why the agent uses MCP instead of direct DB calls.
- How `tools/list` gives the LLM the available tool names/descriptions.
- Why tool selection asks for strict JSON.
- How fallback keyword matching works.
- How raw MCP results are converted into user-facing answers.

## Validation Plan

After implementation:

1. Start REST API on port `8003`.
2. Start MCP server on port `8004`.
3. Confirm Ollama has `mistral:latest`.
4. Start agent on port `8005`.
5. Test:

```text
GET http://127.0.0.1:8005/health
GET http://127.0.0.1:8005/tools
POST http://127.0.0.1:8005/ask
```

Test questions:

```text
List users.
Show me books/resources.
What categories are available?
List authors.
Show available tags.
Show user subscriptions.
Show user bookshelf records.
```

Expected behavior:

- Agent selects the matching MCP tool.
- Agent calls the tool.
- Agent returns a concise answer plus raw result if requested.
- Agent returns developer diagnostics showing tool used, LLM used, temperatures, arguments, and fallback status.

## Implementation Completed

Implemented files:

```text
modules/online_library_agent/__init__.py
modules/online_library_agent/.env.example
modules/online_library_agent/api.py
modules/online_library_agent/config.py
modules/online_library_agent/llm.py
modules/online_library_agent/mcp_client.py
modules/online_library_agent/models.py
modules/online_library_agent/planner.py
modules/online_library_agent/Readme.md
```

Implemented behavior:

- Guided browser UI at `GET /ask`.
- JSON NLQ API at `POST /ask`.
- MCP tool discovery through `tools/list`.
- LLM-based tool selection with local Ollama `mistral:latest`.
- MCP tool call through Streamable HTTP.
- LLM-based answer formatting.
- Deterministic keyword fallback if LLM tool-selection JSON fails.
- Domain guardrail for unrelated questions.
- Developer diagnostics in POC output.

## Implementation Steps After Approval

1. Create `modules/online_library_agent/__init__.py`.
2. Create `.env.example`.
3. Create `config.py`.
4. Create `models.py` for request/response dataclasses or Pydantic models.
5. Create `mcp_client.py`.
6. Create `llm.py` for Ollama calls.
7. Create `planner.py` for tool selection and fallback matching.
8. Create `api.py` with FastAPI endpoints and the guided `/ask` HTML page.
9. Create `Readme.md`.
10. Run compile checks.
11. Start the service on port `8005`.
12. Test representative NLQs against the live MCP server.

## Decisions Confirmed

- User-related tools can be called without confirmation because this is a POC.
- Build the FastAPI `/ask` flow first.
- Do not build CLI in the first version.
- Include guided browser forms/dropdowns so users can quickly get successful results.

## Remaining Question

Please confirm whether the first implementation should include only one combined `/ask` page, or separate pages such as:

```text
/ask
/ask/users
/ask/resources
/ask/subscriptions
```

Recommendation: start with one combined `/ask` page.
