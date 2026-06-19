from __future__ import annotations

from modules.weather_agent.weather_service import Location, WeatherReport, get_weather_report

from .models import WeatherAIRequest


def fetch_current_weather(request: WeatherAIRequest) -> WeatherReport:
    location = Location(city=request.city, state=request.state, country=request.country)
    return get_weather_report(location)


def summarize_weather_report(report: WeatherReport) -> str:
    return "\n".join(
        [
            f"Location: {report.location_label}",
            f"Temperature: {report.temperature_label}",
            f"Condition: {report.condition or 'Not available'}",
            f"Feels like: {report.feels_like_label}",
            f"Humidity: {report.humidity_label}",
            f"Wind: {report.wind_label}",
            f"Source: {report.source}",
        ]
    )
