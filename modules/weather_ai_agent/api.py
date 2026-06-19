from __future__ import annotations

from html import escape

from fastapi import FastAPI, Form, HTTPException, Query
from fastapi.responses import HTMLResponse

from .agent import WeatherAIAgent
from .models import WeatherAIRequest

app = FastAPI(title="Weather AI Agent POC")


def render_page(result_html: str = "") -> HTMLResponse:
    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Weather AI Agent POC</title>
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f5f7fa;
      color: #1d2733;
    }}
    main {{
      max-width: 760px;
      margin: 40px auto;
      padding: 0 20px;
    }}
    form, .result, .error {{
      background: #ffffff;
      border: 1px solid #d9e0e8;
      border-radius: 8px;
      padding: 20px;
      margin-top: 18px;
    }}
    .error {{
      border-color: #d64545;
      color: #8a1f1f;
    }}
    label {{
      display: block;
      font-weight: 700;
      margin: 14px 0 6px;
    }}
    input {{
      box-sizing: border-box;
      width: 100%;
      padding: 10px;
      border: 1px solid #b8c3cf;
      border-radius: 6px;
      font-size: 16px;
    }}
    button {{
      margin-top: 18px;
      padding: 10px 16px;
      border: 0;
      border-radius: 6px;
      background: #246bfe;
      color: #ffffff;
      font-size: 16px;
      cursor: pointer;
    }}
    pre {{
      white-space: pre-wrap;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Weather AI Agent POC</h1>
    <form method="post" action="/weather">
      <label for="city">City</label>
      <input id="city" name="city" value="Atlanta" required>

      <label for="state">State</label>
      <input id="state" name="state" value="GA">

      <label for="country">Country</label>
      <input id="country" name="country" value="US" required>

      <button type="submit">Ask AI Agent</button>
    </form>
    {result_html}
  </main>
</body>
</html>
"""
    return HTMLResponse(html)


def render_agent_result(request: WeatherAIRequest) -> str:
    try:
        response = WeatherAIAgent().get_weather(request)
    except Exception as exc:  # noqa: BLE001 - show user-facing errors in the POC UI.
        return f'<section class="error"><strong>Error:</strong> {escape(str(exc))}</section>'

    return (
        '<section class="result">'
        "<h2>AI Weather Summary</h2>"
        f"<p><strong>Location:</strong> {escape(response.location)}</p>"
        f"<p><strong>Model:</strong> {escape(response.model)}</p>"
        f"<p><strong>Source:</strong> {escape(response.weather_source)}</p>"
        f"<pre>{escape(response.ai_summary)}</pre>"
        "</section>"
    )


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return render_page()


@app.post("/weather", response_class=HTMLResponse)
def weather_form(
    city: str = Form("Atlanta"),
    state: str = Form("GA"),
    country: str = Form("US"),
) -> HTMLResponse:
    request = WeatherAIRequest(city=city, state=state, country=country)
    return render_page(render_agent_result(request))


@app.get("/api/weather")
def weather_api(
    city: str = Query("Atlanta"),
    state: str = Query("GA"),
    country: str = Query("US"),
) -> dict[str, str]:
    request = WeatherAIRequest(city=city, state=state, country=country)
    try:
        response = WeatherAIAgent().get_weather(request)
    except Exception as exc:  # noqa: BLE001 - expose readable POC API error.
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return {
        "location": response.location,
        "model": response.model,
        "weather_source": response.weather_source,
        "raw_weather_summary": response.raw_weather_summary,
        "ai_summary": response.ai_summary,
    }
