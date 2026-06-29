from collections.abc import Iterator
from dataclasses import dataclass
from time import perf_counter

from app.core.config import Settings
from app.schemas.answer_request import AnswerRequest
from app.schemas.answer_response import AnswerComparisonResponse, AnswerResponse, AnswerSource
from app.services.context_builder import ContextBuilder
from app.services.faithfulness_verifier import FaithfulnessVerifier
from app.services.llm_providers.factory import LlmProviderFactory
from app.services.prompt_builder import PromptBuilder
from app.services.search_client import RagSearchClient


class AnswerService:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.search_client = RagSearchClient(settings)
        self.context_builder = ContextBuilder()
        self.prompt_builder = PromptBuilder(
            default_system_instruction=settings.answer_system_instruction,
            synthesis_instruction=settings.answer_synthesis_instruction,
            guardrail_instruction=settings.answer_guardrail_instruction,
        )
        self.verifier = FaithfulnessVerifier()

    def answer(self, request: AnswerRequest) -> AnswerResponse:
        started = perf_counter()
        timings: dict[str, float] = {}
        search_response, context, selected_sources = self._search_and_build_context(request, timings)
        provider_started = perf_counter()
        provider = LlmProviderFactory.build(self.settings)
        timings["llm_provider_build_ms"] = _elapsed_ms(provider_started)
        response = self._generate_answer(
            request=request,
            search_response=search_response,
            context=context,
            selected_sources=selected_sources,
            provider=provider,
            timings=timings,
            started=started,
        )
        return response

    def compare(self, request: AnswerRequest) -> AnswerComparisonResponse:
        started = perf_counter()
        timings: dict[str, float] = {}
        search_response, context, selected_sources = self._search_and_build_context(request, timings)
        model_specs = _parse_model_specs(request.compare_models or _parse_model_list(self.settings.answer_compare_models), self.settings.llm_provider)
        if not model_specs:
            raise ValueError("At least one comparison model is required")

        results = []
        for model_spec in model_specs:
            model_timings = dict(timings)
            try:
                model_started = perf_counter()
                model_settings = _settings_for_model(self.settings, model_spec)
                provider = LlmProviderFactory.build(model_settings)
                model_timings["llm_provider_build_ms"] = _elapsed_ms(model_started)
                results.append(
                    self._generate_answer(
                        request=request,
                        search_response=search_response,
                        context=context,
                        selected_sources=selected_sources,
                        provider=provider,
                        timings=model_timings,
                        started=perf_counter(),
                    )
                )
            except Exception as exc:
                results.append(self._failed_model_response(request, search_response, selected_sources, model_spec, exc))

        include_sources = self.settings.answer_include_sources if request.include_sources is None else request.include_sources

        return AnswerComparisonResponse(
            query=search_response.get("query") or request.query,
            search_mode=search_response.get("search_mode") or request.search_mode,
            search_total_results=int(search_response.get("total_results") or 0),
            context_source_count=len(selected_sources),
            models=[model.display_name for model in model_specs],
            results=results,
            sources=[self._to_source(item) for item in selected_sources] if include_sources else [],
            raw_search=search_response if include_sources else None,
            observability={
                "timings_ms": {"total_ms": round(_elapsed_ms(started), 3)},
                "model_count": len(results),
            }
            if self.settings.answer_observability_enabled
            else None,
        )

    def compare_stream(self, request: AnswerRequest) -> Iterator[dict]:
        started = perf_counter()
        timings: dict[str, float] = {}
        search_response, context, selected_sources = self._search_and_build_context(request, timings)
        model_specs = _parse_model_specs(request.compare_models or _parse_model_list(self.settings.answer_compare_models), self.settings.llm_provider)
        if not model_specs:
            raise ValueError("At least one comparison model is required")

        include_sources = self.settings.answer_include_sources if request.include_sources is None else request.include_sources
        yield {
            "event": "search_complete",
            "query": search_response.get("query") or request.query,
            "search_mode": search_response.get("search_mode") or request.search_mode,
            "search_total_results": int(search_response.get("total_results") or 0),
            "context_source_count": len(selected_sources),
            "models": [model.display_name for model in model_specs],
            "sources": [self._to_source(item).model_dump(mode="json") for item in selected_sources] if include_sources else [],
        }

        completed = 0
        for model_spec in model_specs:
            yield {
                "event": "model_started",
                "completed": completed,
                "total": len(model_specs),
                "model": model_spec.display_name,
            }
            model_timings = dict(timings)
            try:
                model_started = perf_counter()
                model_settings = _settings_for_model(self.settings, model_spec)
                provider = LlmProviderFactory.build(model_settings)
                model_timings["llm_provider_build_ms"] = _elapsed_ms(model_started)
                result = self._generate_answer(
                    request=request,
                    search_response=search_response,
                    context=context,
                    selected_sources=selected_sources,
                    provider=provider,
                    timings=model_timings,
                    started=perf_counter(),
                )
            except Exception as exc:
                result = self._failed_model_response(request, search_response, selected_sources, model_spec, exc)
            completed += 1
            yield {
                "event": "model_result",
                "completed": completed,
                "total": len(model_specs),
                "result": result.model_dump(mode="json"),
            }

        yield {
            "event": "complete",
            "completed": completed,
            "total": len(model_specs),
            "total_ms": round(_elapsed_ms(started), 3),
        }

    def _failed_model_response(
        self,
        request: AnswerRequest,
        search_response: dict,
        selected_sources: list[dict],
        model_spec,
        error: Exception,
    ) -> AnswerResponse:
        include_sources = self.settings.answer_include_sources if request.include_sources is None else request.include_sources
        return AnswerResponse(
            query=search_response.get("query") or request.query,
            answer=f"Model failed: {type(error).__name__}: {error}",
            answer_status="failed",
            answer_mode=request.answer_mode,
            llm_provider=model_spec.provider,
            llm_model=model_spec.model,
            search_mode=search_response.get("search_mode") or request.search_mode,
            search_total_results=int(search_response.get("total_results") or 0),
            context_source_count=len(selected_sources),
            citation_verification={"supported": False, "reason": "model_generation_failed"},
            sources=[self._to_source(item) for item in selected_sources] if include_sources else [],
        )

    def _search_and_build_context(
        self,
        request: AnswerRequest,
        timings: dict[str, float],
    ) -> tuple[dict, str, list[dict]]:
        search_started = perf_counter()
        search_response = self.search_client.search(request)
        timings["search_request_ms"] = _elapsed_ms(search_started)
        context_top_k = request.context_top_k or self.settings.answer_context_top_k
        context_started = perf_counter()
        context, selected_sources = self.context_builder.build(
            search_response=search_response,
            context_top_k=context_top_k,
            max_chars=self.settings.answer_max_context_chars,
            query=search_response.get("query") or request.query,
            max_chars_per_source=self.settings.answer_max_chars_per_source,
        )
        timings["context_packing_ms"] = _elapsed_ms(context_started)
        return search_response, context, selected_sources

    def _generate_answer(
        self,
        request: AnswerRequest,
        search_response: dict,
        context: str,
        selected_sources: list[dict],
        provider,
        timings: dict[str, float],
        started: float,
    ) -> AnswerResponse:
        include_sources = self.settings.answer_include_sources if request.include_sources is None else request.include_sources
        prompt = None
        answer_status = "answered"
        cited_source_ranks: list[int] = []
        verification = {}
        if not context and self.settings.answer_require_context:
            answer = "I could not find enough retrieved context to answer this question without guessing."
            answer_status = "insufficient_context"
            verification = {
                "supported": False,
                "reason": "no_selected_context",
                "cited_source_ranks": [],
                "missing_citations": True,
            }
        else:
            prompt = self.prompt_builder.build(
                query=request.query,
                context=context,
                system_instruction=request.system_instruction,
                answer_mode=request.answer_mode,
            )
            llm_started = perf_counter()
            answer = provider.generate(prompt)
            timings["llm_generation_ms"] = _elapsed_ms(llm_started)
            verification_started = perf_counter()
            verification_result = self.verifier.verify(answer, selected_sources, query=request.query)
            timings["faithfulness_verification_ms"] = _elapsed_ms(verification_started)
            verification = verification_result.to_dict()
            cited_source_ranks = verification_result.cited_source_ranks
            if answer.strip().lower().startswith("insufficient_context"):
                answer = "I could not find enough retrieved context to answer this question without guessing."
                answer_status = "insufficient_context"
            elif not verification_result.supported:
                answer = self._insufficient_context_answer(verification_result.reason)
                answer_status = "insufficient_context"
        timings.setdefault("llm_generation_ms", 0.0)
        timings.setdefault("faithfulness_verification_ms", 0.0)
        timings["total_ms"] = _elapsed_ms(started)

        return AnswerResponse(
            query=search_response.get("query") or request.query,
            answer=answer,
            answer_status=answer_status,
            answer_mode=request.answer_mode,
            llm_provider=provider.provider_name,
            llm_model=provider.model,
            search_mode=search_response.get("search_mode") or request.search_mode,
            search_total_results=int(search_response.get("total_results") or 0),
            context_source_count=len(selected_sources),
            cited_source_ranks=cited_source_ranks,
            citation_verification=verification,
            sources=[self._to_source(item) for item in selected_sources] if include_sources else [],
            raw_search=search_response if include_sources else None,
            raw_prompt=prompt if request.include_raw_prompt else None,
            observability=self._observability_payload(search_response, selected_sources, timings) if self.settings.answer_observability_enabled else None,
        )

    def _to_source(self, item: dict) -> AnswerSource:
        return AnswerSource(
            rank=int(item.get("rank") or 0),
            resource_id=str(item.get("resource_id") or ""),
            chunk_id=str(item.get("chunk_id") or ""),
            title=str(item.get("title") or ""),
            chunk_index=int(item.get("chunk_index") or 0),
            page_start=item.get("page_start"),
            page_end=item.get("page_end"),
            section_title=item.get("section_title"),
            score=float(item.get("score") or 0.0),
            snippet=str(item.get("snippet") or ""),
        )

    def _insufficient_context_answer(self, reason: str) -> str:
        return (
            "I could not verify the generated answer against the retrieved context, "
            f"so I cannot answer without guessing. Verification reason: {reason}."
        )

    def _observability_payload(self, search_response: dict, selected_sources: list[dict], timings: dict[str, float]) -> dict:
        return {
            "timings_ms": {key: round(value, 3) for key, value in timings.items()},
            "search_observability": search_response.get("observability"),
            "selected_sources": [
                {
                    "rank": int(item.get("rank") or 0),
                    "chunk_id": str(item.get("chunk_id") or ""),
                    "chunk_index": int(item.get("chunk_index") or 0),
                    "score": float(item.get("score") or 0.0),
                }
                for item in selected_sources
            ],
        }


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000.0


def _parse_model_list(value: str) -> list[str]:
    models = []
    seen = set()
    for item in value.split(","):
        model = item.strip()
        if model and model not in seen:
            seen.add(model)
            models.append(model)
    return models


@dataclass(frozen=True)
class CompareModelSpec:
    provider: str
    model: str

    @property
    def display_name(self) -> str:
        return f"{self.provider}:{self.model}"


def _parse_model_specs(values: list[str], default_provider: str) -> list[CompareModelSpec]:
    specs = []
    seen = set()
    for value in values:
        provider, model = _parse_model_spec(value, default_provider)
        key = (provider, model)
        if model and key not in seen:
            seen.add(key)
            specs.append(CompareModelSpec(provider=provider, model=model))
    return specs


def _parse_model_spec(value: str, default_provider: str) -> tuple[str, str]:
    normalized = value.strip()
    for provider in ("ollama", "gemini", "openai"):
        prefix = f"{provider}:"
        if normalized.startswith(prefix):
            return provider, normalized[len(prefix) :].strip()
    return default_provider, normalized


def _settings_for_model(settings: Settings, model_spec: CompareModelSpec) -> Settings:
    if model_spec.provider == "ollama":
        return settings.model_copy(update={"llm_provider": "ollama", "llm_model": model_spec.model})
    if model_spec.provider == "gemini":
        return settings.model_copy(update={"llm_provider": "gemini", "gemini_model": model_spec.model})
    if model_spec.provider == "openai":
        return settings.model_copy(update={"llm_provider": "openai", "openai_model": model_spec.model})
    raise ValueError(f"Unsupported comparison provider: {model_spec.provider}")
