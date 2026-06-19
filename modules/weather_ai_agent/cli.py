from __future__ import annotations

import argparse
import sys

from .agent import WeatherAIAgent
from .models import WeatherAIRequest


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ask the Gemini-powered Weather AI Agent.")
    parser.add_argument("--city", default="Atlanta", help="City name. Default: Atlanta")
    parser.add_argument("--state", default="GA", help="State or region. Default: GA")
    parser.add_argument("--country", default="US", help="Country code/name. Default: US")
    parser.add_argument("--verbose", action="store_true", help="Show CrewAI execution details.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    request = WeatherAIRequest(city=args.city, state=args.state, country=args.country)
    try:
        response = WeatherAIAgent(verbose=args.verbose).get_weather(request)
    except RuntimeError as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
    except Exception as exc:  # noqa: BLE001 - keep CLI errors readable for this POC.
        print(f"Weather AI Agent error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    print(f"Location: {response.location}")
    print(f"Model: {response.model}")
    print(f"Weather source: {response.weather_source}")
    print()
    print(response.ai_summary)


if __name__ == "__main__":
    main()
