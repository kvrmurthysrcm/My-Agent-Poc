The essential difference is:

> `weather_agent` retrieves and returns weather facts deterministically.  
> `weather_ai_agent` reuses the same retrieval code, then asks an LLM to convert those facts into a natural-language summary.

## Implementation comparison

| Area | `weather_agent` | `weather_ai_agent` |
|---|---|---|
| Weather retrieval | Directly retrieves weather | Reuses `weather_agent` retrieval |
| Data sources | weather.com, then wttr.in fallback | Same sources through `weather_agent` |
| LLM used | No | Yes |
| AI framework | Creates a CrewAI `Agent` object if CrewAI is installed, but never runs it | Runs CrewAI `Agent`, `Task`, and `Crew` |
| Model providers | None | Gemini or Ollama |
| Main result | Structured `WeatherReport` | Raw weather summary plus generated prose |
| Determinism | High | Weather facts are deterministic; wording is generated |
| Latency and cost | One weather-network operation | Weather-network operation plus LLM inference |
| Required configuration | None beyond network access | `LLM_PROVIDER`, model, endpoint, and possibly API key |
| Kubernetes port | `8006` | `8007` |
| Kubernetes memory limit | 256 MiB | 1 GiB |

## Weather Agent flow

The regular implementation is:

```text
Request
  → WeatherAgent.current_weather()
  → get_weather_report()
  → weather.com
  → fallback to wttr.in if needed
  → WeatherReport
  → structured HTML or JSON response
```

Its public method simply delegates to the deterministic service:

```python
def current_weather(self, location=None):
    return get_weather_report(location or Location())
```

See [agent.py](D:/py-workspace/My-Agent-Poc/modules/weather_agent/agent.py:38) and [weather_service.py](D:/py-workspace/My-Agent-Poc/modules/weather_agent/weather_service.py:75).

Although it constructs a CrewAI `Agent` object when CrewAI is available, that object is never given a task and is never executed. Also, CrewAI is not included in this module’s runtime requirements.

Therefore, the name “agent” is somewhat generous: technically, it is a deterministic weather-service facade.

Its API returns fields such as:

```json
{
  "location": {},
  "temperature_f": 72,
  "temperature_c": 22.2,
  "condition": "Partly Cloudy",
  "humidity": 60,
  "wind": "8 mph NW",
  "source": "..."
}
```

## Weather AI Agent flow

The AI implementation is:

```text
Request
  → fetch_current_weather()
  → reuse weather_agent.get_weather_report()
  → structured WeatherReport
  → convert observations into a factual text block
  → create CrewAI Task
  → run Crew with Gemini or Ollama
  → generated weather explanation
  → return raw facts and AI summary
```

See [agent.py](D:/py-workspace/My-Agent-Poc/modules/weather_ai_agent/agent.py:39).

The LLM receives facts similar to:

```text
Location: Atlanta, GA, US
Temperature: 72 F / 22.2 C
Condition: Partly Cloudy
Feels like: 72 F
Humidity: 60%
Wind: 8 mph NW
Source: ...
```

It is instructed to produce a concise response, mention the source, and add one practical note. The Agent backstory also asks for clothing or hydration advice.

The API returns both the grounding data and generated answer:

```json
{
  "location": "Atlanta, GA, US",
  "model": "configured-model",
  "weather_source": "...",
  "raw_weather_summary": "...",
  "ai_summary": "It is currently partly cloudy..."
}
```

## Important architectural point

The AI version does **not** let the LLM autonomously call the weather tool.

`fetch_current_weather()` is called directly before the CrewAI task is created:

```python
report = fetch_current_weather(request)
raw_summary = summarize_weather_report(report)
crew.kickoff()
```

Therefore, this is a grounded two-stage pipeline:

```text
Deterministic retrieval → LLM summarization
```

It is not an autonomous agent loop:

```text
LLM decides whether to call tool → tool executes → LLM evaluates result
```

That is a good design for weather because the LLM cannot invent or independently determine live conditions.

## MCP relationship

Neither module uses MCP.

The function named `weather_tool.py` is an ordinary Python adapter. It is not:

- An MCP tool
- Registered through `@mcp.tool()`
- A CrewAI-decorated tool
- Dynamically selected by the model

## Operational trade-off

Use `weather_agent` when you need:

- Fast responses
- Predictable JSON
- Lower infrastructure requirements
- No model dependency
- Easy automated testing

Use `weather_ai_agent` when you need:

- A conversational explanation
- Plain-language interpretation
- Clothing, hydration, or practical suggestions
- More natural user-facing output

One weakness shared by both: `/health` only returns `{"status": "ok"}`. It does not verify weather providers, and the AI version does not verify Gemini or Ollama readiness.