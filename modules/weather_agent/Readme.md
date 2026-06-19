# Weather Agent POC

This module contains a single CrewAI-backed Weather Agent POC. It gets current temperature and weather details for a configurable location, defaulting to Atlanta, GA, US.

The implementation tries weather.com first. If weather.com blocks or does not expose readable current-condition data, it falls back to `wttr.in` and includes the source URL in the output.

## Files

- `agent.py` - Single Weather Agent facade.
- `weather_service.py` - Weather lookup and parsing logic.
- `cli.py` - Command prompt entrypoint.
- `api.py` - FastAPI web UI and JSON API.

## Setup

From the project root:

```powershell
.\.venv\Scripts\python.exe -m pip install -e .
```

If `pip` is not available in the virtual environment:

```powershell
.\.venv\Scripts\python.exe -m ensurepip --upgrade
.\.venv\Scripts\python.exe -m pip install -e .
```

## Run From Command Prompt

Default location:

```powershell
.\.venv\Scripts\python.exe -m modules.weather_agent.cli
```

Custom location:

```powershell
.\.venv\Scripts\python.exe -m modules.weather_agent.cli --city Atlanta --state GA --country US
```

Example output:

```text
Location: Atlanta, GA, US
Temperature: 82 F / 27.8 C
Condition: Partly Cloudy
Feels like: 84 F
Humidity: 61%
Wind: 7 mph NW
Source: https://weather.com/weather/today/l/Atlanta+GA+US
```

## Run The Web Interface

Start FastAPI from the project root:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.weather_agent.api:app --reload
```

Open:

```text
http://127.0.0.1:8000
```

The page has a simple form for city, state, and country. Submit the form to display current weather details.

## JSON API

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/weather?city=Atlanta&state=GA&country=US"
```

## Notes

- CrewAI is used to define the single Weather Agent.
- The weather data retrieval is deterministic and does not require an LLM API key.
- For future POCs, create a separate folder under `modules/` with its own `Readme.md`.
