from __future__ import annotations

from dataclasses import dataclass, field

from .weather_service import Location, WeatherReport, get_weather_report

try:
    from crewai import Agent
except ImportError:  # pragma: no cover - documented install path covers this.
    Agent = None  # type: ignore[assignment]


@dataclass(slots=True)
class WeatherAgent:
    """Single-agent facade for getting current weather details."""

    verbose: bool = False
    agent: object | None = field(init=False, default=None)

    def __post_init__(self) -> None:
        self.agent = self._build_crewai_agent()

    def _build_crewai_agent(self):
        if Agent is None:
            return None

        return Agent(
            role="Weather Information Agent",
            goal="Get the current temperature and weather details for a requested location.",
            backstory=(
                "You retrieve current weather details from weather.com when available "
                "and return concise, user-readable observations."
            ),
            verbose=self.verbose,
            allow_delegation=False,
        )

    def current_weather(self, location: Location | None = None) -> WeatherReport:
        return get_weather_report(location or Location())
