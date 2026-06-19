# Online Library NLQ Agent

FastAPI-based natural-language agent for querying Online Library data through MCP tools.

## Required Services

Start the Online Library REST API:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.online_library.api:app --reload --port 8003
```

Start the Online Library MCP server:

```powershell
.\.venv\Scripts\python.exe -m modules.online_library_mcp.server
```

Make sure Ollama has the configured model:

```powershell
ollama pull mistral:latest
```

## Run The Agent

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.online_library_agent.api:app --reload --port 8005
```

Open:

```text
http://127.0.0.1:8005/ask
```

## Configuration

Create `modules/online_library_agent/.env` if you want to override defaults:

```env
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=mistral:latest
ONLINE_LIBRARY_MCP_URL=http://127.0.0.1:8004/mcp
ONLINE_LIBRARY_AGENT_HOST=127.0.0.1
ONLINE_LIBRARY_AGENT_PORT=8005
ONLINE_LIBRARY_AGENT_TIMEOUT_SECONDS=120
ONLINE_LIBRARY_AGENT_DEFAULT_LIMIT=10
ONLINE_LIBRARY_TOOL_SELECTION_TEMPERATURE=0.1
ONLINE_LIBRARY_ANSWER_TEMPERATURE=0.2
ONLINE_LIBRARY_TOOL_SELECTION_NUM_PREDICT=160
ONLINE_LIBRARY_ANSWER_NUM_PREDICT=220
```

## Endpoints

- `GET /health`
- `GET /tools`
- `GET /ask`
- `POST /ask`

The `/ask` page includes guided forms for common questions and an open-ended question box.

## Developer Diagnostics

The POC shows internal details in the result:

- MCP tool used
- tool arguments
- LLM provider and model
- Ollama URL
- MCP URL
- temperatures
- max generated token settings
- fallback status
- timing values

These details are useful for development and can be hidden later in a real app.
