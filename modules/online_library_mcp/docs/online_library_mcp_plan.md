# Online Library MCP Server Plan

## Status

Approved and implemented.

## Recommended Module Name

Use:

```text
modules/online_library_mcp/
```

Reason:

- Lowercase Python package naming.
- Clear relationship to `modules/online_library`.
- Explicit that this module is the MCP layer, not the database API itself.

## Goal

Create an MCP server that exposes tools on top of the existing Online Library FastAPI API.

The intended flow:

```text
Agent / MCP Client
        |
        | MCP Streamable HTTP
        v
online_library_mcp server
        |
        | HTTP JSON calls
        v
online_library FastAPI API
        |
        | SQL SELECT queries
        v
PostgreSQL online_library DB
```

This keeps the MCP layer separate from direct database access. The MCP tools will call the existing HTTP API rather than opening PostgreSQL connections themselves.

## Transport Requirement

Use MCP Streamable HTTP.

Do not use the old HTTP+SSE transport.

Important current MCP details:

- MCP messages are JSON-RPC.
- Streamable HTTP uses a single MCP endpoint, typically `/mcp`.
- Clients send JSON-RPC messages with HTTP `POST`.
- The older HTTP+SSE transport from MCP protocol version `2024-11-05` has been replaced by Streamable HTTP.
- The Python MCP SDK supports `mcp.run(transport="streamable-http")`.
- For scalable deployments, the Python SDK recommends `FastMCP(..., stateless_http=True, json_response=True)`.

For this module, use JSON responses, not SSE streaming responses:

```python
FastMCP("OnlineLibraryMCP", stateless_http=True, json_response=True)
```

Then run:

```python
mcp.run(transport="streamable-http")
```

## Proposed MCP Endpoint

Default MCP endpoint:

```text
http://127.0.0.1:8004/mcp
```

Expected run command after implementation:

```powershell
.\.venv\Scripts\python.exe -m modules.online_library_mcp.server
```

Alternative if mounted into an ASGI app later:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.online_library_mcp.app:app --reload --port 8004
```

The first implementation can use the SDK's built-in Streamable HTTP runner for simplicity.

## Dependency Plan

Add the official MCP Python SDK:

```text
mcp
```

The project already has:

```text
httpx
fastapi
uvicorn
```

The MCP server itself does not need `psycopg`, because it will call `online_library` over HTTP.

## Configuration

Use environment variables:

```env
ONLINE_LIBRARY_API_BASE_URL=http://127.0.0.1:8003
ONLINE_LIBRARY_MCP_HOST=127.0.0.1
ONLINE_LIBRARY_MCP_PORT=8004
```

For Kubernetes or Docker later:

```env
ONLINE_LIBRARY_API_BASE_URL=http://online-library-api:8003
```

## Proposed Folder Structure

```text
modules/online_library_mcp/
  __init__.py
  config.py
  client.py
  tools.py
  server.py
  Readme.md
  docs/
    online_library_mcp_plan.md
```

Optional later:

```text
modules/online_library_mcp/
  tests/
  postman/
```

Postman is less useful for MCP because MCP uses JSON-RPC envelopes, but a small HTTP smoke collection can be added later if useful.

## Tool Design

The current `online_library` API exposes table SELECT endpoints for non-empty tables.

The MCP tools should wrap those endpoints into agent-friendly functions.

### Tool 1: `list_available_tables`

Purpose:

- Let the agent discover which library tables are available.

Underlying API:

```text
GET /tables
```

Tool input:

```json
{}
```

Tool output:

```json
{
  "count": 13,
  "tables": [
    {
      "table": "resources",
      "order_column": "resource_id"
    }
  ]
}
```

### Tool 2: `get_authors`

Purpose:

- Fetch author records.

Underlying API:

```text
GET /authors?limit={limit}&offset={offset}
```

Tool input:

```json
{
  "limit": 20,
  "offset": 0
}
```

### Tool 3: `get_categories`

Purpose:

- Fetch category records.

Underlying API:

```text
GET /categories?limit={limit}&offset={offset}
```

### Tool 4: `get_resources`

Purpose:

- Fetch resource/book records.
- This will likely be the most useful tool for an agent.

Underlying API:

```text
GET /resources?limit={limit}&offset={offset}
```

Tool input:

```json
{
  "limit": 20,
  "offset": 0
}
```

### Tool 5: `get_tags`

Purpose:

- Fetch tag records for topic discovery.

Underlying API:

```text
GET /tags?limit={limit}&offset={offset}
```

### Tool 6: `get_subscription_tiers`

Purpose:

- Fetch available subscription tiers.

Underlying API:

```text
GET /subscription-tiers?limit={limit}&offset={offset}
```

### Tool 7: `get_user_bookshelf`

Purpose:

- Fetch user bookshelf records.
- Useful for later personalized agent flows.

Underlying API:

```text
GET /user-bookshelf?limit={limit}&offset={offset}
```

### Tool 8: `get_user_subscriptions`

Purpose:

- Fetch user subscription records.

Underlying API:

```text
GET /user-subscriptions?limit={limit}&offset={offset}
```

## Implemented Tool Set

The implementation exposes all 13 non-empty table endpoints as MCP tools, plus one discovery tool.

Implemented tools:

```text
list_available_tables
get_authors
get_categories
get_library_users
get_reading_progress
get_resource_authors
get_resource_tags
get_resources
get_subscription_rules
get_subscription_tiers
get_tags
get_user_approval_requests
get_user_bookshelf
get_user_subscriptions
```

User-related tools are included for the POC even though there is no auth yet.

## Agent Integration Plan

After the MCP server exists, create a new agent module or extend the existing weather-agent pattern with an Online Library agent.

Recommended new module later:

```text
modules/online_library_agent/
```

Purpose:

- Connect to the MCP server as a tool source.
- Let an LLM ask library questions using MCP tools.
- Keep the MCP server reusable by any MCP-compatible client.

Suggested flow:

```text
User asks: "Show me available architecture books."
        |
        v
Online Library Agent
        |
        v
MCP client calls get_resources
        |
        v
online_library_mcp tool
        |
        v
online_library API /resources
        |
        v
Agent summarizes results
```

## Why Keep MCP Separate From The API?

Reasons:

- The FastAPI module remains a simple REST/JSON API.
- The MCP module can evolve independently.
- The same API can serve browser/Postman clients and MCP tools.
- MCP tool descriptions can be tuned for agents without changing REST endpoint behavior.
- Later, auth can be added at the API layer, MCP layer, or both.

## Streamable HTTP Design Notes

Implementation should follow these choices:

- Use one MCP endpoint: `/mcp`.
- Use `stateless_http=True` for simpler scaling.
- Use `json_response=True` to avoid SSE response streaming.
- Bind locally to `127.0.0.1` for local development.
- Add a clear warning before binding to `0.0.0.0`.
- Validate `ONLINE_LIBRARY_API_BASE_URL` at startup or first tool call.

For browser-based MCP clients later, CORS may be needed, especially for the `Mcp-Session-Id` header. The first version does not need browser CORS unless a browser MCP client is used.

## Security Notes

No authentication is required for the current POC, but this is not production-safe.

Risks:

- The Online Library API exposes user data.
- MCP tools make that data easier for an agent to access.
- A malicious prompt could ask the agent to dump all available tables.
- Local MCP servers should not be exposed on public interfaces without auth.

Later production requirements:

- Add API auth.
- Add MCP auth.
- Add tool-level allowlists.
- Add pagination limits.
- Add audit logging.
- Consider hiding user email fields from MCP tools.
- Add origin validation if exposed over HTTP to clients.

## Error Handling Plan

The MCP tools should return structured errors when:

- The Online Library API is down.
- A request times out.
- The API returns non-2xx status.
- The API response is not valid JSON.
- The requested limit or offset is invalid.

Suggested client timeout:

```text
10 seconds
```

Suggested retry policy:

- No retries in first version.
- Add retries later only for idempotent GETs if needed.

## Validation Plan

After implementation:

1. Start Online Library API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.online_library.api:app --reload --port 8003
```

2. Start MCP server:

```powershell
.\.venv\Scripts\python.exe -m modules.online_library_mcp.server
```

3. Verify MCP endpoint is reachable:

```text
http://127.0.0.1:8004/mcp
```

4. Use an MCP-compatible client to initialize and list tools.

5. Call at least five tools:

```text
list_available_tables
get_resources
get_authors
get_categories
get_tags
```

6. Confirm each tool returns JSON from the Online Library API.

## Implementation Completed

Completed files:

```text
modules/online_library_mcp/__init__.py
modules/online_library_mcp/config.py
modules/online_library_mcp/client.py
modules/online_library_mcp/tools.py
modules/online_library_mcp/server.py
modules/online_library_mcp/Readme.md
```

Completed behavior:

1. Added `mcp` to `pyproject.toml`.
2. Created environment-based MCP configuration.
3. Created an `httpx` client for the Online Library API.
4. Created all 13 non-empty table tools.
5. Created `list_available_tables`.
6. Created Streamable HTTP server with `FastMCP(..., stateless_http=True, json_response=True)`.
7. Kept MCP port `8004`.
8. Included user-related tools.
9. Validated the MCP server with a real Streamable HTTP MCP client session.

## References

- MCP Streamable HTTP transport specification: https://modelcontextprotocol.io/specification/2025-06-18/basic/transports
- Official MCP Python SDK: https://github.com/modelcontextprotocol/python-sdk
