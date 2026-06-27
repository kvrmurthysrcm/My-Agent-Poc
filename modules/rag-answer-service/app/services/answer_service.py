from app.core.config import Settings
from app.schemas.answer_request import AnswerRequest
from app.schemas.answer_response import AnswerResponse, AnswerSource
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
        self.prompt_builder = PromptBuilder()
        self.verifier = FaithfulnessVerifier()

    def answer(self, request: AnswerRequest) -> AnswerResponse:
        search_response = self.search_client.search(request)
        context_top_k = request.context_top_k or self.settings.answer_context_top_k
        context, selected_sources = self.context_builder.build(
            search_response=search_response,
            context_top_k=context_top_k,
            max_chars=self.settings.answer_max_context_chars,
            query=search_response.get("query") or request.query,
            max_chars_per_source=self.settings.answer_max_chars_per_source,
        )
        include_sources = self.settings.answer_include_sources if request.include_sources is None else request.include_sources

        provider = LlmProviderFactory.build(self.settings)
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
            answer = provider.generate(prompt)
            verification_result = self.verifier.verify(answer, selected_sources)
            verification = verification_result.to_dict()
            cited_source_ranks = verification_result.cited_source_ranks
            if answer.strip().lower().startswith("insufficient_context"):
                answer = "I could not find enough retrieved context to answer this question without guessing."
                answer_status = "insufficient_context"
            elif not verification_result.supported:
                answer = self._insufficient_context_answer(verification_result.reason)
                answer_status = "insufficient_context"

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
