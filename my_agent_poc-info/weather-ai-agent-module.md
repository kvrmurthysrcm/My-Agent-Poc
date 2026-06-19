# Weather AI Agent Module

Module path:

```text
modules/weather_ai_agent/
```

This module wraps the deterministic weather lookup module with a CrewAI agent backed by a configured LLM. The LLM does not fetch live weather directly. Live weather facts come from `modules.weather_agent.weather_service`, and the LLM is used only to produce a concise natural-language explanation.

## Files

- `__init__.py`: exports `WeatherAIAgent`, `WeatherAIRequest`, and `WeatherAIResponse`.
- `agent.py`: creates the CrewAI agent, task, crew, and final AI response.
- `api.py`: provides FastAPI browser and JSON API execution.
- `cli.py`: provides shell execution.
- `config.py`: loads Gemini or Ollama configuration from environment variables.
- `models.py`: defines request and response dataclasses.
- `weather_tool.py`: adapts the deterministic weather module for AI use.
- `Readme.md`: explains setup and basic commands.
- `docs/weather_ai_agent_plan.md`: records the implementation plan.
- `docs/weather_ai_agent_prompt.md`: records the original prompt.

## Main Data Objects

`WeatherAIRequest` represents the user request.

It has:

- `city`
- `state`
- `country`

It also has `location_label`, which joins non-empty fields into a display label.

`WeatherAIResponse` represents the AI module response.

It has:

- `location`
- `weather_source`
- `raw_weather_summary`
- `ai_summary`
- `model`

## Configuration Control Flow

LLM configuration is loaded by `load_llm_config()` in `config.py`.

Control flow:

1. Load a module-local `.env` file if present.
2. Read `LLM_PROVIDER`, defaulting to `gemini`.
3. If the provider is `ollama`, read `OLLAMA_MODEL` and `OLLAMA_BASE_URL`.
4. If the provider is `gemini`, read and validate `GEMINI_API_KEY`.
5. Return a frozen `LLMConfig`.

The AI module can run with either a valid Gemini key or a reachable local Ollama server.

## Agent Control Flow

`WeatherAIAgent` is defined in `agent.py`.

When `WeatherAIAgent()` is created:

1. Store the `verbose` setting.
2. Load Gemini configuration.
3. Create a CrewAI `LLM` with the configured provider.
4. Create a CrewAI `Agent` named `AI Weather Advisor`.
5. Configure the agent to avoid delegation and to use only supplied live observations.

When `get_weather(request)` is called:

1. `fetch_current_weather(request)` runs.
2. That function converts `WeatherAIRequest` to `modules.weather_agent.weather_service.Location`.
3. It calls `get_weather_report(location)` from the deterministic module.
4. The returned `WeatherReport` is converted to text with `summarize_weather_report(report)`.
5. A CrewAI `Task` is created with the raw weather observations in the prompt.
6. A CrewAI `Crew` is created with one agent and one task.
7. `crew.kickoff()` sends the task to Gemini through CrewAI.
8. The returned AI output is converted to string.
9. A `WeatherAIResponse` is returned with both raw weather details and the AI summary.

## What Happens From The Shell

Typical command:

```powershell
.\.venv\Scripts\python.exe -m modules.weather_ai_agent.cli --city Dallas --state TX --country US
```

Shell flow:

1. Python runs `modules.weather_ai_agent.cli`.
2. `cli.py` builds an argument parser.
3. The parser reads `--city`, `--state`, `--country`, and `--verbose`.
4. A `WeatherAIRequest` object is created.
5. `WeatherAIAgent(verbose=args.verbose)` is constructed.
6. Gemini configuration is loaded.
7. `get_weather(request)` fetches live weather through the deterministic module.
8. The raw weather report is summarized into text.
9. CrewAI sends a task to Gemini.
10. The CLI prints location, model, weather source, and the AI summary.

If `GEMINI_API_KEY` is missing or still a placeholder, the CLI prints a configuration error to standard error and exits with code `2`.

For other runtime errors, the CLI prints a weather-agent error and exits with code `1`.

## What Happens From The Browser

Typical server command:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.weather_ai_agent.api:app --reload --port 8002
```

Browser flow:

1. Uvicorn imports `modules.weather_ai_agent.api`.
2. FastAPI uses the `app` object declared in `api.py`.
3. The user opens `http://127.0.0.1:8002`.
4. FastAPI calls `home()`.
5. `home()` returns `render_page()`, which contains an HTML form.
6. The user submits the form to `POST /weather`.
7. `weather_form()` receives `city`, `state`, and `country` from form fields.
8. A `WeatherAIRequest` object is created.
9. `render_agent_result(request)` calls `WeatherAIAgent().get_weather(request)`.
10. The deterministic weather module fetches live weather.
11. The configured LLM summarizes the weather through CrewAI.
12. The result is escaped and rendered into an HTML result section.
13. If an exception occurs, the browser receives an inline error section.

## What Happens From The JSON API

Typical request:

```powershell
Invoke-RestMethod "http://127.0.0.1:8002/api/weather?city=Atlanta&state=GA&country=US"
```

API flow:

1. FastAPI calls `weather_api()`.
2. Query parameters are read with defaults.
3. A `WeatherAIRequest` object is created.
4. `WeatherAIAgent().get_weather(request)` is called.
5. The deterministic weather module fetches live weather.
6. CrewAI sends the summarization task to the configured LLM.
7. FastAPI returns a JSON object containing location, model, weather source, raw weather summary, and AI summary.

If any exception occurs, the API returns HTTP `502` with the exception text in the response detail.

## Relationship To `weather_agent`

This module depends on `modules.weather_agent.weather_service`.

The dependency is one-way:

```text
weather_ai_agent -> weather_agent.weather_service
```

The deterministic module does not call the AI module. This keeps live weather lookup reusable without requiring Gemini.

## Limitations

- Requires a valid Gemini API key when `LLM_PROVIDER=gemini`.
- Requires a running local Ollama server when `LLM_PROVIDER=ollama`.
- Requires network access to weather data sources, and to the LLM provider when it is remote.
- Gemini can still produce wording that is broader than the raw observations, even though the prompt asks it not to invent facts.
- There is no schema validation for the final LLM text.
- There is no retry, timeout, or fallback strategy around the Gemini call in this module.
- The browser UI catches all exceptions and displays raw exception text, which is useful for a POC but not ideal for production.
- The JSON API maps all failures to HTTP `502`, even configuration errors.
- There is no persistence, conversation memory, or request history.
- The LLM call adds latency and cost compared with the deterministic module.

## Possible Upgrades

- Add response validation so the AI output must include required fields.
- Add a deterministic fallback summary if Gemini is unavailable.
- Separate configuration errors from upstream service errors in the API.
- Add retries and explicit timeouts for LLM calls.
- Add structured observability for weather fetch time and Gemini response time.
- Add tests that mock weather lookup and CrewAI output.
- Add prompt versioning.
- Add support for user questions such as travel advice, outdoor activity planning, or hourly forecasts.
- Add server-side templates instead of inline HTML.

## Further Details

Please confirm if you want this document to include prompt-by-prompt CrewAI execution details or examples of actual Gemini responses.
