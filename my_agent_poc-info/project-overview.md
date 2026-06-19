# My Agent POC Project Overview

This project contains proof-of-concept weather agents under the `modules` package.

There are two main modules:

- `modules.weather_agent`: deterministic weather lookup with a CLI, browser form, and JSON API.
- `modules.weather_ai_agent`: Gemini-backed CrewAI agent that first fetches live weather data, then asks an LLM to summarize it.

The project uses Python packaging through `pyproject.toml`, so modules are expected to run from the repository root with Python module commands.

## Repository Structure

```text
My-Agent-Poc/
  main.py
  pyproject.toml
  prompts/
  modules/
    weather_agent/
    weather_ai_agent/
  my_agent_poc-info/
```

`main.py` is still the default PyCharm sample script. It is not connected to either weather agent.

## Shared Runtime Model

Both weather modules expose two user-facing paths:

1. Shell execution through a module CLI.
2. Browser or HTTP execution through a FastAPI app.

The deterministic module can run without an LLM key. The AI module requires `GEMINI_API_KEY` because it uses Gemini through CrewAI for the final natural-language response.

## Shell Control Flow

When a user runs a shell command such as:

```powershell
.\.venv\Scripts\python.exe -m modules.weather_agent.cli
```

Python imports the requested module and executes its `main()` function because the file contains:

```python
if __name__ == "__main__":
    main()
```

The CLI then:

1. Builds an `argparse.ArgumentParser`.
2. Reads command-line arguments.
3. Creates a request or location object.
4. Calls the module's agent facade.
5. Prints the result to standard output.

## Browser Control Flow

When a user starts a FastAPI app with Uvicorn, for example:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.weather_agent.api:app --reload
```

Uvicorn imports `modules.weather_agent.api`, finds the `app` object, and starts an HTTP server.

The browser path then works like this:

1. The user opens `http://127.0.0.1:8000`.
2. FastAPI calls the `GET /` handler.
3. The handler returns an HTML form.
4. The user submits the form.
5. FastAPI calls the `POST /weather` handler.
6. The handler builds a request or location object.
7. The module's agent facade runs.
8. The result is rendered into HTML and returned to the browser.

Both FastAPI apps also expose `GET /api/weather`, which returns JSON instead of HTML.

## Dependencies

The project dependencies are defined in `pyproject.toml`:

- `crewai[google-genai]`
- `fastapi`
- `httpx`
- `python-dotenv`
- `uvicorn[standard]`

The deterministic weather module uses `httpx` for live HTTP requests. The AI weather module uses the deterministic module for weather data, then uses CrewAI and Gemini for summarization.

## Limitations

- `main.py` is unrelated to the weather modules and may confuse new users.
- There are no automated tests in the repository.
- The project has no single top-level command entrypoint.
- The web pages are generated as inline HTML strings rather than templates.
- There is no centralized error-handling layer across both modules.
- Live weather behavior depends on external websites and network access.

## Possible Upgrades

- Add console scripts in `pyproject.toml` for easier commands.
- Add unit tests for parsing, request models, CLI argument handling, and API routes.
- Replace inline HTML with templates.
- Add structured logging.
- Add a top-level README that explains both modules together.
- Add typed configuration for ports, defaults, timeouts, and model selection.
- Add CI checks for formatting, linting, and tests.

## Further Details

Please confirm if you want these docs to include sequence diagrams, call graphs, or beginner-level Python explanations.
