from __future__ import annotations

import argparse

from .agent import WeatherAgent
from .weather_service import Location


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Get current weather details.")
    parser.add_argument("--city", default="Atlanta", help="City name. Default: Atlanta")
    parser.add_argument("--state", default="GA", help="State or region. Default: GA")
    parser.add_argument("--country", default="US", help="Country code/name. Default: US")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    location = Location(city=args.city, state=args.state, country=args.country)
    report = WeatherAgent().current_weather(location)

    print(f"Location: {report.location_label}")
    print(f"Temperature: {report.temperature_label}")
    print(f"Condition: {report.condition or 'Not available'}")
    print(f"Feels like: {report.feels_like_label}")
    print(f"Humidity: {report.humidity_label}")
    print(f"Wind: {report.wind_label}")
    print(f"Source: {report.source}")


if __name__ == "__main__":
    main()
