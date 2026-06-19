from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from typing import Any

import httpx

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/125.0 Safari/537.36"
)


@dataclass(slots=True)
class Location:
    city: str = "Atlanta"
    state: str = "GA"
    country: str = "US"

    @property
    def label(self) -> str:
        parts = [self.city.strip(), self.state.strip(), self.country.strip()]
        return ", ".join(part for part in parts if part)

    @property
    def weather_com_path(self) -> str:
        parts = [self.city.strip(), self.state.strip(), self.country.strip()]
        return "+".join(part.replace(" ", "+") for part in parts if part)


@dataclass(slots=True)
class WeatherReport:
    location: Location
    temperature_f: float | None = None
    temperature_c: float | None = None
    condition: str | None = None
    feels_like_f: float | None = None
    humidity: int | None = None
    wind: str | None = None
    source: str = "unknown"

    @property
    def location_label(self) -> str:
        return self.location.label

    @property
    def temperature_label(self) -> str:
        return _temperature_label(self.temperature_f, self.temperature_c)

    @property
    def feels_like_label(self) -> str:
        return _temperature_label(self.feels_like_f, None)

    @property
    def humidity_label(self) -> str:
        return f"{self.humidity}%" if self.humidity is not None else "Not available"

    @property
    def wind_label(self) -> str:
        return self.wind or "Not available"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["location"] = asdict(self.location)
        data["location_label"] = self.location_label
        data["temperature_label"] = self.temperature_label
        data["feels_like_label"] = self.feels_like_label
        data["humidity_label"] = self.humidity_label
        data["wind_label"] = self.wind_label
        return data


def get_weather_report(location: Location) -> WeatherReport:
    with httpx.Client(headers={"User-Agent": USER_AGENT}, follow_redirects=True, timeout=15) as client:
        report = _fetch_from_weather_com(client, location)
        if report is not None:
            return report
        return _fetch_from_wttr(client, location)


def _fetch_from_weather_com(client: httpx.Client, location: Location) -> WeatherReport | None:
    url = f"https://weather.com/weather/today/l/{location.weather_com_path}"
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError:
        return None

    text = response.text
    temp_f = _extract_number(text, r'"temperature":\s*(-?\d+(?:\.\d+)?)')
    condition = _extract_text(
        text,
        (
            r'"wxPhraseLong":\s*"([^"]+)"',
            r'"phrase":\s*"([^"]+)"',
            r'"description":\s*"([^"]+)"',
        ),
    )
    feels_like = _extract_number(text, r'"temperatureFeelsLike":\s*(-?\d+(?:\.\d+)?)')
    humidity = _extract_int(text, r'"relativeHumidity":\s*(\d+)')
    wind_speed = _extract_number(text, r'"windSpeed":\s*(-?\d+(?:\.\d+)?)')
    wind_direction = _extract_text(text, (r'"windDirectionCardinal":\s*"([^"]+)"',))

    if temp_f is None and condition is None:
        return None

    wind = None
    if wind_speed is not None:
        wind = f"{wind_speed:g} mph"
        if wind_direction:
            wind = f"{wind} {wind_direction}"

    return WeatherReport(
        location=location,
        temperature_f=temp_f,
        temperature_c=_fahrenheit_to_celsius(temp_f),
        condition=condition,
        feels_like_f=feels_like,
        humidity=humidity,
        wind=wind,
        source=url,
    )


def _fetch_from_wttr(client: httpx.Client, location: Location) -> WeatherReport:
    query = location.label.replace(" ", "+")
    url = f"https://wttr.in/{query}?format=j1"
    response = client.get(url)
    response.raise_for_status()
    payload = response.json()
    current = payload["current_condition"][0]

    condition = None
    descriptions = current.get("weatherDesc") or []
    if descriptions:
        condition = descriptions[0].get("value")

    wind = current.get("windspeedMiles")
    wind_direction = current.get("winddir16Point")
    wind_label = f"{wind} mph" if wind else None
    if wind_label and wind_direction:
        wind_label = f"{wind_label} {wind_direction}"

    temp_f = _to_float(current.get("temp_F"))
    return WeatherReport(
        location=location,
        temperature_f=temp_f,
        temperature_c=_to_float(current.get("temp_C")) or _fahrenheit_to_celsius(temp_f),
        condition=condition,
        feels_like_f=_to_float(current.get("FeelsLikeF")),
        humidity=_to_int(current.get("humidity")),
        wind=wind_label,
        source=url,
    )


def _extract_number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text)
    return _to_float(match.group(1)) if match else None


def _extract_int(text: str, pattern: str) -> int | None:
    match = re.search(pattern, text)
    return _to_int(match.group(1)) if match else None


def _extract_text(text: str, patterns: tuple[str, ...]) -> str | None:
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            return match.group(1)
    return None


def _fahrenheit_to_celsius(value: float | None) -> float | None:
    return round((value - 32) * 5 / 9, 1) if value is not None else None


def _temperature_label(temp_f: float | None, temp_c: float | None) -> str:
    if temp_f is None and temp_c is None:
        return "Not available"
    if temp_f is None:
        return f"{temp_c:g} C"
    if temp_c is None:
        return f"{temp_f:g} F"
    return f"{temp_f:g} F / {temp_c:g} C"


def _to_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None
