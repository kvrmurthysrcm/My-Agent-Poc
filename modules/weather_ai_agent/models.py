from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class WeatherAIRequest:
    city: str = "Atlanta"
    state: str = "GA"
    country: str = "US"

    @property
    def location_label(self) -> str:
        parts = [self.city.strip(), self.state.strip(), self.country.strip()]
        return ", ".join(part for part in parts if part)


@dataclass(slots=True)
class WeatherAIResponse:
    location: str
    weather_source: str
    raw_weather_summary: str
    ai_summary: str
    model: str
