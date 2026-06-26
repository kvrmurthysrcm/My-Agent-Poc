from sqlalchemy.orm import Session

from app.core.config import Settings
from app.repositories.rag_search_repository import RagSearchRepository
from app.schemas.search_request import SearchRequest
from app.schemas.search_response import SearchResponse, SearchResultItem
from app.search.filters import to_filter_set
from app.search.lexical import token_counts
from app.search.query_preprocessor import QueryPreprocessor
from app.search.result_quality import clean_result_text, is_searchable_result_text, is_short_boilerplate_text
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
        self.query_preprocessor = QueryPreprocessor()
        self.snippet_builder = SnippetBuilder()
        self.hybrid_service = HybridSearchService()
        self.ranking_service = RankingService()
        self.reranking_service = RerankingService()

    def search(self, request: SearchRequest) -> SearchResponse:
        query = self.query_preprocessor.normalize(request.query)
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
        candidates = self._retrieve(mode, query, filters, top_k)
        candidates = [
            item
            for item in candidates
            if not is_short_boilerplate_text(item.get("chunk_text") or "")
            and (
                float(item.get("resource_match_score") or 0.0) > 0.0
                or is_searchable_result_text(item.get("chunk_text") or "")
            )
        ]
        if self.settings.rerank_enabled:
            candidates = self.reranking_service.rerank(
                query=query,
                items=candidates,
                top_n=max(top_k, self.settings.rerank_top_n),
            )
        ranked = self.ranking_service.rank(candidates, min_score=min_score, limit=top_k)
        results = [
            self._to_result_item(index + 1, item, query, request.include_metadata, include_chunk_text)
            for index, item in enumerate(ranked)
        ]
        return SearchResponse(
            query=query,
            search_mode=mode,
            top_k=top_k,
            total_results=len(results),
            embedding_provider=self.settings.embedding_provider.value,
            embedding_model=self.settings.embedding_model,
            results=results,
        )

    def _retrieve(self, mode: str, query: str, filters, top_k: int) -> list[dict]:
        vector_results: list[dict] = []
        keyword_results: list[dict] = []
        retrieve_k = top_k
        if mode == "hybrid":
            retrieve_k = min(self.settings.search_max_top_k * self.settings.hybrid_oversampling_factor, top_k * self.settings.hybrid_oversampling_factor)

        if mode in {"vector", "hybrid"}:
            provider = EmbeddingProviderFactory.build(self.settings)
            query_vector = provider.embed_texts([query])[0]
            vector_results = self.repository.vector_search(
                query_vector=query_vector,
                filters=filters,
                top_k=retrieve_k,
                provider=self.settings.embedding_provider.value,
                model=self.settings.embedding_model,
                version=self.settings.embedding_version,
                dimension=self.settings.embedding_dimension or len(query_vector),
            )
            for item in vector_results:
                item["score"] = float(item.get("vector_score") or 0.0)

        if mode in {"keyword", "hybrid"}:
            keyword_results = self.repository.keyword_search(query=query, filters=filters, top_k=retrieve_k)
            for item in keyword_results:
                item["resource_match_score"] = max(
                    float(item.get("resource_match_score") or 0.0),
                    _resource_match_score(query, item.get("title") or ""),
                )
                item["score"] = float(item.get("keyword_score") or 0.0)

        if mode == "hybrid":
            return self.hybrid_service.merge(
                vector_results=vector_results,
                keyword_results=keyword_results,
                vector_weight=self.settings.search_vector_weight,
                keyword_weight=self.settings.search_keyword_weight,
                fusion_strategy=self.settings.hybrid_fusion_strategy,
                rrf_k=self.settings.rrf_k,
            )
        return vector_results if mode == "vector" else keyword_results

    def _to_result_item(
        self,
        rank: int,
        item: dict,
        query: str,
        include_metadata: bool,
        include_chunk_text: bool,
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
        )


def _round_optional(value) -> float | None:
    if value is None:
        return None
    return round(float(value), 6)


def _resource_match_score(query: str, title: str) -> float:
    query_terms = set(token_counts(query))
    title_terms = set(token_counts(title))
    if not query_terms or not title_terms:
        return 0.0
    title_overlap = len(title_terms & query_terms) / len(title_terms)
    query_overlap = len(title_terms & query_terms) / len(query_terms)
    if title_overlap == 1.0:
        return 2.0
    if title_overlap >= 0.5 or query_overlap >= 0.5:
        return 1.0
    return 0.0
