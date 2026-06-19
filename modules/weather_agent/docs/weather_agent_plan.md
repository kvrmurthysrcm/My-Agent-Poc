# Weather Agent POC Plan

## Folder Structure

- Keep this POC under `modules/weather_agent/`.
- Keep implementation, CLI, API, and module-specific `Readme.md` in that folder.
- Keep original prompts under the project-level `prompts/` folder.

## Implementation

1. Create a single Weather Agent module.
2. Use CrewAI for the agent definition, while keeping the weather lookup deterministic so it can run without an LLM API key.
3. Default the location to Atlanta, GA, US.
4. Allow the location to be configured with `city`, `state`, and `country`.
5. Fetch weather data from weather.com first.
6. If weather.com cannot be read directly, use a no-key fallback weather endpoint and clearly report the source used.
7. Provide a command-line runner.
8. Provide one FastAPI app with:
   - A simple web form.
   - A JSON API endpoint.
   - Rendered weather details after submission.
9. Document setup and execution in `modules/weather_agent/Readme.md`.

## Execution

CLI:

```powershell
.\.venv\Scripts\python.exe -m modules.weather_agent.cli --city Atlanta --state GA --country US
```

FastAPI:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.weather_agent.api:app --reload
```

Then open:

```text
http://127.0.0.1:8000
```
