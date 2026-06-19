# Weather AI Agent Plan

## Goal

Create an AI-based weather agent that accepts a city or city/state/country and returns a Gemini-generated weather response.

## Important Design Point

An LLM should not be trusted as the live weather source. The agent will fetch current weather observations from an HTTP weather source, then use Gemini through CrewAI to explain those observations in a concise user-facing answer.

## Folder

All files for this POC live under:

```text
modules/weather_ai_agent/
```

## Configuration

Gemini is configured with environment variables:

```powershell
$env:GEMINI_API_KEY="your-key"
$env:GEMINI_MODEL="gemini-2.5-flash"
```

`GEMINI_MODEL` is optional and defaults to `gemini-2.5-flash`.

## Execution

Default Atlanta request:

```powershell
.\.venv\Scripts\python.exe -m modules.weather_ai_agent.cli
```

Custom city/state:

```powershell
.\.venv\Scripts\python.exe -m modules.weather_ai_agent.cli --city Dallas --state TX --country US
```

Web UI:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.weather_ai_agent.api:app --reload --port 8002
```

## Verification

Until a real Gemini API key is configured, syntax and import checks can be run. Full AI execution requires `GEMINI_API_KEY`.
