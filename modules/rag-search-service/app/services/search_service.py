from time import perf_counter

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.rag_search_repository import RagSearchRepository
from app.schemas.search_request import SearchRequest
from app.schemas.search_response import SearchResponse, SearchResultItem
from app.search.filters import to_filter_set
from app.search.lexical import token_counts
from app.search.query_preprocessor import QueryPreprocessor, QueryUnderstanding
from app.search.result_quality import (
    clean_result_text,
    is_searchable_chunk_metadata,
    is_searchable_result_text,
    is_short_boilerplate_text,
)
from app.search.snippet_builder import SnippetBuilder
from app.services.embedding_providers.factory import EmbeddingProviderFactory
from app.services.hybrid_search_service import HybridSearchService
from app.services.ranking_service import RankingService
from app.services.reranking_service import RerankingService


class SearchService:
    def __init__(self, db: Session, settings: Settings):
        self.db = db
        self.settings = settings
        self.repository = RagSearchRepository(db)
        self.query_preprocessor = QueryPreprocessor(settings.query_aliases)
        self.snippet_builder = SnippetBuilder()
        self.hybrid_service = HybridSearchService()
        self.ranking_service = RankingService()
        self.reranking_service = RerankingService(settings.query_aliases)

    def search(self, request: SearchRequest) -> SearchResponse:
        return self._search(request, include_debug=self.settings.search_observability_enabled)

    def debug_search(self, request: SearchRequest) -> SearchResponse:
        if not self.settings.search_observability_enabled:
            raise ValueError("Search observability is disabled. Set SEARCH_OBSERVABILITY_ENABLED=true to use debug search.")
        return self._search(request, include_debug=True)

    def _search(self, request: SearchRequest, include_debug: bool) -> SearchResponse:
        started = perf_counter()
        timings: dict[str, float] = {}
        debug: dict = {"candidates": {}} if include_debug else {}

        query_info = self.query_preprocessor.understand(request.query)
        query = query_info.normalized_query
        mode = request.search_mode or self.settings.search_default_mode
        top_k = request.top_k or self.settings.search_default_top_k
        min_score = self.settings.search_min_score if request.min_score is None else request.min_score
        include_chunk_text = (
            self.settings.search_include_chunk_text_default
            if request.include_chunk_text is None
            else request.include_chunk_text
        )

        if top_k > self.settings.search_max_top_k:
            raise ValueError(f"top_k must be {self.settings.search_max_top_k} or lower")

        filters = to_filter_set(request.filters if self.settings.search_enable_metadata_filters else None)
        candidates = self._retrieve(mode, query_info, filters, top_k, timings=timings, debug=debug if include_debug else None)
        before_quality_count = len(candidates)
        quality_started = perf_counter()
        kept_candidates = []
        filtered_candidates = []
        for item in candidates:
            keep, reason = self._quality_decision(item)
            item["quality_filter_reason"] = reason
            if keep:
                kept_candidates.append(item)
            elif include_debug:
                filtered_candidates.append(self._debug_candidate(item, reason=reason))
        candidates = kept_candidates
        timings["quality_filter_ms"] = _elapsed_ms(quality_started)
        if include_debug:
            debug["candidates"]["after_merge_count"] = before_quality_count
            debug["candidates"]["after_quality_filter_count"] = len(candidates)
            debug["candidates"]["filtered"] = filtered_candidates[: self.settings.search_max_top_k]

        if self.settings.rerank_enabled:
            rerank_started = perf_counter()
            candidates = self.reranking_service.rerank(
                query=query,
                query_intent=query_info.query_intent,
                items=candidates,
                top_n=max(top_k, self.settings.rerank_top_n),
            )
            timings["reranking_ms"] = _elapsed_ms(rerank_started)
        else:
            timings["reranking_ms"] = 0.0

        ranking_started = perf_counter()
        ranked = self.ranking_service.rank(candidates, min_score=min_score, limit=top_k)
        timings["final_ranking_ms"] = _elapsed_ms(ranking_started)
        results = [
            self._to_result_item(index + 1, item, query, request.include_metadata, include_chunk_text, include_debug)
            for index, item in enumerate(ranked)
        ]
        timings["total_ms"] = _elapsed_ms(started)

        return SearchResponse(
            query=query,
            original_query=query_info.original_query,
            query_intent=query_info.query_intent,
            spelling_normalized=query_info.spelling_normalized,
            search_mode=mode,
            top_k=top_k,
            total_results=len(results),
            embedding_provider=self.settings.embedding_provider.value,
            embedding_model=self.settings.embedding_model,
            results=results,
            observability=self._observability_payload(query_info, mode, top_k, timings, debug) if include_debug else None,
        )

    def _retrieve(
        self,
        mode: str,
        query_info: QueryUnderstanding,
        filters,
        top_k: int,
        timings: dict[str, float],
        debug: dict | None = None,
    ) -> list[dict]:
        query = query_info.normalized_query
        vector_results: list[dict] = []
        keyword_results: list[dict] = []
        retrieve_k = top_k
        if mode == "hybrid":
            retrieve_k = min(self.settings.search_max_top_k * self.settings.hybrid_oversampling_factor, top_k * self.settings.hybrid_oversampling_factor)

        if mode in {"vector", "hybrid"}:
            embedding_started = perf_counter()
            provider = EmbeddingProviderFactory.build(self.settings)
            query_vector = provider.embed_texts([query])[0]
            timings["query_embedding_ms"] = _elapsed_ms(embedding_started)
            vector_started = perf_counter()
            vector_results = self.repository.vector_search(
                query_vector=query_vector,
                filters=filters,
                top_k=retrieve_k,
                provider=self.settings.embedding_provider.value,
                model=self.settings.embedding_model,
                version=self.settings.embedding_version,
                dimension=self.settings.embedding_dimension or len(query_vector),
            )
            timings["vector_db_retrieval_ms"] = _elapsed_ms(vector_started)
            for item in vector_results:
                item["score"] = float(item.get("vector_score") or 0.0)
            if debug is not None:
                debug["query_embedding_model"] = {
                    "provider": self.settings.embedding_provider.value,
                    "model": self.settings.embedding_model,
                    "version": self.settings.embedding_version,
                    "dimension": self.settings.embedding_dimension or len(query_vector),
                }
                debug["candidates"]["vector_count"] = len(vector_results)
                debug["candidates"]["vector"] = [self._debug_candidate(item) for item in vector_results]
        else:
            timings["query_embedding_ms"] = 0.0
            timings["vector_db_retrieval_ms"] = 0.0

        if mode in {"keyword", "hybrid"}:
            keyword_started = perf_counter()
            keyword_results = self.repository.keyword_search(
                query=query,
                filters=filters,
                top_k=retrieve_k,
                query_intent=query_info.query_intent,
            )
            for item in keyword_results:
                item["resource_match_score"] = max(
                    float(item.get("resource_match_score") or 0.0),
                    _resource_match_score(query, item.get("title") or "", self.settings.query_aliases),
                )
                item["score"] = float(item.get("keyword_score") or 0.0)
            timings["keyword_db_retrieval_ms"] = _elapsed_ms(keyword_started)
            if debug is not None:
                debug["candidates"]["keyword_count"] = len(keyword_results)
                debug["candidates"]["keyword"] = [self._debug_candidate(item) for item in keyword_results]
        else:
            timings["keyword_db_retrieval_ms"] = 0.0

        if mode == "hybrid":
            merge_started = perf_counter()
            merged = self.hybrid_service.merge(
                vector_results=vector_results,
                keyword_results=keyword_results,
                vector_weight=self.settings.search_vector_weight,
                keyword_weight=self.settings.search_keyword_weight,
                fusion_strategy=self.settings.hybrid_fusion_strategy,
                rrf_k=self.settings.rrf_k,
            )
            timings["hybrid_merge_ms"] = _elapsed_ms(merge_started)
            if debug is not None:
                debug["candidates"]["merged_count"] = len(merged)
                debug["candidates"]["merged"] = [self._debug_candidate(item) for item in merged]
            return merged
        timings["hybrid_merge_ms"] = 0.0
        return vector_results if mode == "vector" else keyword_results

    def _to_result_item(
        self,
        rank: int,
        item: dict,
        query: str,
        include_metadata: bool,
        include_chunk_text: bool,
        include_debug: bool,
    ) -> SearchResultItem:
        metadata = None
        if include_metadata:
            metadata = {
                "resource": item.get("resource_metadata") or {},
                "chunk": item.get("chunk_metadata") or {},
            }
        display_text = clean_result_text(item.get("chunk_text") or "")
        return SearchResultItem(
            rank=rank,
            resource_id=str(item["resource_id"]),
            chunk_id=str(item["chunk_id"]),
            title=item.get("title") or "",
            chunk_index=int(item.get("chunk_index") or 0),
            page_start=item.get("page_start"),
            page_end=item.get("page_end"),
            section_title=item.get("section_title"),
            heading_path=item.get("heading_path") or [],
            score=round(float(item.get("score") or 0.0), 6),
            vector_score=_round_optional(item.get("vector_score")),
            keyword_score=_round_optional(item.get("keyword_score")),
            snippet=self.snippet_builder.build(display_text, query),
            chunk_text=display_text if include_chunk_text else None,
            metadata=metadata,
            debug=self._result_debug(item) if include_debug else None,
        )

    def _quality_decision(self, item: dict) -> tuple[bool, str]:
        metadata = item.get("chunk_metadata") or {}
        text = item.get("chunk_text") or ""
        if not is_searchable_chunk_metadata(metadata):
            return False, "chunk_metadata_not_searchable"
        if is_short_boilerplate_text(text):
            return False, "short_boilerplate_text"
        if float(item.get("resource_match_score") or 0.0) > 0.0:
            return True, "resource_metadata_match"
        if not is_searchable_result_text(
            text,
            keep_numeric_table_chunks=self.settings.search_keep_numeric_table_chunks,
            min_alpha_ratio=self.settings.search_min_alpha_ratio,
        ):
            return False, "low_value_result_text"
        return True, "searchable_text"

    def _result_debug(self, item: dict) -> dict:
        reasons = []
        if item.get("exact_phrase_match"):
            reasons.append("exact_phrase_match")
        if item.get("resource_match_score"):
            reasons.append("resource_match")
        if item.get("rerank_score") is not None:
            reasons.append("reranked")
        if item.get("quality_filter_reason"):
            reasons.append(str(item["quality_filter_reason"]))
        return {
            "vector_rank": item.get("vector_rank"),
            "keyword_rank": item.get("keyword_rank"),
            "vector_score": _round_optional(item.get("vector_score")),
            "keyword_score": _round_optional(item.get("keyword_score")),
            "rrf_score": _round_optional(item.get("rrf_score")),
            "retrieval_score": _round_optional(item.get("retrieval_score")),
            "rerank_score": _round_optional(item.get("rerank_score")),
            "resource_match_score": _round_optional(item.get("resource_match_score")),
            "quality_filter_reason": item.get("quality_filter_reason"),
            "final_score": _round_optional(item.get("score")),
            "ranking_reasons": reasons,
        }

    def _debug_candidate(self, item: dict, reason: str | None = None) -> dict:
        return {
            "chunk_id": str(item.get("chunk_id") or ""),
            "resource_id": str(item.get("resource_id") or ""),
            "title": item.get("title") or "",
            "chunk_index": int(item.get("chunk_index") or 0),
            "vector_score": _round_optional(item.get("vector_score")),
            "keyword_score": _round_optional(item.get("keyword_score")),
            "rrf_score": _round_optional(item.get("rrf_score")),
            "retrieval_score": _round_optional(item.get("retrieval_score")),
            "rerank_score": _round_optional(item.get("rerank_score")),
            "resource_match_score": _round_optional(item.get("resource_match_score")),
            "score": _round_optional(item.get("score")),
            "reason": reason or item.get("quality_filter_reason"),
        }

    def _observability_payload(
        self,
        query_info: QueryUnderstanding,
        mode: str,
        top_k: int,
        timings: dict[str, float],
        debug: dict,
    ) -> dict:
        return {
            "normalized_query": query_info.normalized_query,
            "original_query": query_info.original_query,
            "query_intent": query_info.query_intent,
            "spelling_normalized": query_info.spelling_normalized,
            "search_mode": mode,
            "top_k": top_k,
            "timings_ms": {key: round(value, 3) for key, value in timings.items()},
            **debug,
        }


def _round_optional(value) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _elapsed_ms(started: float) -> float:
    return (perf_counter() - started) * 1000.0


def _resource_match_score(query: str, title: str, aliases: dict[str, str] | None = None) -> float:
    query_terms = set(token_counts(query, aliases=aliases))
    title_terms = set(token_counts(title, aliases=aliases))
    if not query_terms or not title_terms:
        return 0.0
    title_overlap = len(title_terms & query_terms) / len(title_terms)
    query_overlap = len(title_terms & query_terms) / len(query_terms)
    if title_overlap == 1.0:
        return 2.0
    if title_overlap >= 0.5 or query_overlap >= 0.5:
        return 1.0
    return 0.0
