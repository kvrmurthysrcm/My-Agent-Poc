from __future__ import annotations

from html import escape

from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse

from .agent import WeatherAgent
from .weather_service import Location

app = FastAPI(title="Weather Agent POC")


def render_page(result_html: str = "") -> HTMLResponse:
    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Weather Agent POC</title>
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
    form, .result {{
      background: #ffffff;
      border: 1px solid #d9e0e8;
      border-radius: 8px;
      padding: 20px;
      margin-top: 18px;
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
    dt {{
      font-weight: 700;
      margin-top: 10px;
    }}
    dd {{
      margin: 4px 0 0;
    }}
  </style>
</head>
<body>
  <main>
    <h1>Weather Agent POC</h1>
    <form method="post" action="/weather">
      <label for="city">City</label>
      <input id="city" name="city" value="Atlanta" required>

      <label for="state">State</label>
      <input id="state" name="state" value="GA">

      <label for="country">Country</label>
      <input id="country" name="country" value="US" required>

      <button type="submit">Get Weather</button>
    </form>
    {result_html}
  </main>
</body>
</html>
"""
    return HTMLResponse(html)


def report_to_html(location: Location) -> str:
    report = WeatherAgent().current_weather(location)
    fields = {
        "Location": report.location_label,
        "Temperature": report.temperature_label,
        "Condition": report.condition or "Not available",
        "Feels Like": report.feels_like_label,
        "Humidity": report.humidity_label,
        "Wind": report.wind_label,
        "Source": report.source,
    }
    details = "\n".join(
        f"<dt>{escape(label)}</dt><dd>{escape(value)}</dd>"
        for label, value in fields.items()
    )
    return f'<section class="result"><h2>Current Weather</h2><dl>{details}</dl></section>'


@app.get("/", response_class=HTMLResponse)
def home() -> HTMLResponse:
    return render_page()


@app.post("/weather", response_class=HTMLResponse)
def weather_form(
    city: str = Form("Atlanta"),
    state: str = Form("GA"),
    country: str = Form("US"),
) -> HTMLResponse:
    location = Location(city=city, state=state, country=country)
    return render_page(report_to_html(location))


@app.get("/api/weather")
def weather_api(
    city: str = Query("Atlanta"),
    state: str = Query("GA"),
    country: str = Query("US"),
) -> dict[str, object]:
    location = Location(city=city, state=state, country=country)
    return WeatherAgent().current_weather(location).to_dict()
