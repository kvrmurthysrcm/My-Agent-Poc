# Weather Agent Module

Module path:

```text
modules/weather_agent/
```

This module retrieves current weather details without requiring an LLM API key. It defines a CrewAI agent facade when CrewAI is installed, but the actual weather lookup is deterministic Python code in `weather_service.py`.

## Files

- `__init__.py`: exports `Location`, `WeatherAgent`, and `WeatherReport`.
- `agent.py`: defines the `WeatherAgent` facade.
- `weather_service.py`: fetches and parses weather data.
- `cli.py`: provides shell execution.
- `api.py`: provides FastAPI browser and JSON API execution.
- `Readme.md`: explains setup and basic commands.
- `docs/weather_agent_plan.md`: records the implementation plan.

## Main Data Objects

`Location` represents the requested place.

It has:

- `city`
- `state`
- `country`

It also provides:

- `label`: human-readable form, such as `Atlanta, GA, US`.
- `weather_com_path`: URL path form, such as `Atlanta+GA+US`.

`WeatherReport` represents the weather result.

It stores raw values such as temperature, condition, humidity, wind, and source. It also exposes display labels such as `temperature_label`, `humidity_label`, and `wind_label`.

## Agent Control Flow

`WeatherAgent` is defined in `agent.py`.

When `WeatherAgent()` is created:

1. `__post_init__()` runs because this is a dataclass.
2. `_build_crewai_agent()` tries to create a CrewAI `Agent`.
3. If CrewAI is unavailable, the internal `agent` field is set to `None`.
4. The module can still fetch weather because weather lookup does not depend on CrewAI.

When `current_weather()` is called:

1. It accepts a `Location`.
2. If no location is provided, it defaults to `Location()`, which is Atlanta, GA, US.
3. It calls `get_weather_report()` from `weather_service.py`.
4. It returns a `WeatherReport`.

## Weather Lookup Control Flow

`get_weather_report(location)` performs the live weather lookup.

Control flow:

1. Create an `httpx.Client` with a browser-like user agent, redirects enabled, and a 15 second timeout.
2. Try `_fetch_from_weather_com(client, location)`.
3. If weather.com returns readable current-condition data, return that report.
4. If weather.com fails or cannot be parsed, call `_fetch_from_wttr(client, location)`.
5. Return the fallback report from `wttr.in`.

The weather.com parser searches the HTML response text with regular expressions for fields such as:

- `temperature`
- `wxPhraseLong`
- `temperatureFeelsLike`
- `relativeHumidity`
- `windSpeed`
- `windDirectionCardinal`

If both temperature and condition are missing, the module treats weather.com as unusable and falls back to `wttr.in`.

## What Happens From The Shell

Typical command:

```powershell
.\.venv\Scripts\python.exe -m modules.weather_agent.cli --city Atlanta --state GA --country US
```

Shell flow:

1. Python runs `modules.weather_agent.cli`.
2. `cli.py` builds an argument parser.
3. The parser reads `--city`, `--state`, and `--country`.
4. A `Location` object is created.
5. `WeatherAgent().current_weather(location)` is called.
6. `weather_service.py` fetches live data.
7. A `WeatherReport` is returned.
8. The CLI prints location, temperature, condition, feels-like temperature, humidity, wind, and source.

If no arguments are provided, the default location is Atlanta, GA, US.

## What Happens From The Browser

Typical server command:

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.weather_agent.api:app --reload
```

Browser flow:

1. Uvicorn imports `modules.weather_agent.api`.
2. FastAPI uses the `app` object declared in `api.py`.
3. The user opens `http://127.0.0.1:8000`.
4. FastAPI calls `home()`.
5. `home()` returns `render_page()`, which contains an HTML form.
6. The user submits the form to `POST /weather`.
7. `weather_form()` receives `city`, `state`, and `country` from form fields.
8. A `Location` object is created.
9. `report_to_html(location)` calls `WeatherAgent().current_weather(location)`.
10. The returned `WeatherReport` is converted into escaped HTML.
11. The full page is returned to the browser with the result section included.

## What Happens From The JSON API

Typical request:

```powershell
Invoke-RestMethod "http://127.0.0.1:8000/api/weather?city=Atlanta&state=GA&country=US"
```

API flow:

1. FastAPI calls `weather_api()`.
2. Query parameters are read with defaults.
3. A `Location` object is created.
4. `WeatherAgent().current_weather(location)` is called.
5. `WeatherReport.to_dict()` converts the dataclass to a dictionary.
6. FastAPI serializes the dictionary as JSON.

## Limitations

- Weather.com parsing depends on regular expressions against page content, so site changes can break it.
- The fallback source, `wttr.in`, is also external and can fail or rate-limit requests.
- There is no caching, so every request performs live HTTP calls.
- There is no retry policy beyond weather.com fallback.
- Location handling is simple string formatting, not geocoding.
- The FastAPI HTML is inline inside Python code.
- Exceptions from the fallback weather request can still bubble up and fail the CLI or API request.
- The CrewAI agent object is not used to reason or call tools in this module.

## Possible Upgrades

- Use a stable weather API with an API key and documented response schema.
- Add geocoding and validation for ambiguous city names.
- Add retries with backoff for transient HTTP failures.
- Cache recent weather responses by location.
- Add tests for weather.com parsing and wttr.in JSON parsing.
- Add user-friendly error pages and JSON error responses.
- Move browser HTML into templates.
- Add logging for selected source, request duration, and failures.

## Further Details

Please confirm if you want deeper implementation notes for each helper function in `weather_service.py`.
