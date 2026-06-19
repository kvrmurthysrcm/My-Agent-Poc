from __future__ import annotations

from crewai import Agent, Crew, LLM, Process, Task

from .config import load_llm_config
from .models import WeatherAIRequest, WeatherAIResponse
from .weather_tool import fetch_current_weather, summarize_weather_report


class WeatherAIAgent:
    """CrewAI weather agent that uses a configured LLM to explain live weather data."""

    def __init__(self, verbose: bool = False) -> None:
        self.verbose = verbose
        self.config = load_llm_config()
        self.llm = LLM(
            model=self.config.model,
            provider=self.config.provider,
            api_key=self.config.api_key,
            base_url=self.config.base_url,
            temperature=0.2,
        )
        self.agent = Agent(
            role="AI Weather Advisor",
            goal=(
                "Explain current weather conditions clearly using only the supplied "
                "live weather observations."
            ),
            backstory=(
                "You are a concise weather assistant. You do not invent live weather. "
                "You interpret provided observations and give practical, plain-English guidance."
                "Add dress code advisory if any like carry water bottle, hat etc."
            ),
            llm=self.llm,
            verbose=verbose,
            allow_delegation=False,
        )

    def get_weather(self, request: WeatherAIRequest) -> WeatherAIResponse:
        report = fetch_current_weather(request)
        raw_summary = summarize_weather_report(report)
        task = Task(
            description=(
                "Create a concise weather response for the user.\n\n"
                "Use only the weather observations below. Do not add facts that are not present.\n\n"
                f"{raw_summary}\n\n"
                "Include the current temperature, condition, feels-like temperature, humidity, "
                "wind, and one short practical note."
            ),
            expected_output=(
                "A concise natural-language weather summary. Mention the weather data source "
                "at the end."
            ),
            agent=self.agent,
        )
        crew = Crew(
            agents=[self.agent],
            tasks=[task],
            process=Process.sequential,
            verbose=self.verbose,
        )
        output = crew.kickoff()

        return WeatherAIResponse(
            location=report.location_label,
            weather_source=report.source,
            raw_weather_summary=raw_summary,
            ai_summary=str(output),
            model=self.config.model,
        )
