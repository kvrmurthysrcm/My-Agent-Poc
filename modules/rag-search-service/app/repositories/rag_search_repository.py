import json
import math
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Category, RagChunkEmbedding, RagDocumentChunk, Resource, ResourceTag, Tag
from app.search.filters import SearchFilterSet
from app.search.lexical import phrase_in_text, token_counts, tokenize_meaningful


class RagSearchRepository:
    def __init__(self, db: Session):
        self.db = db

    def vector_search(
        self,
        query_vector: list[float],
        filters: SearchFilterSet,
        top_k: int,
        provider: str,
        model: str,
        version: str,
        dimension: int,
    ) -> list[dict]:
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            return self._postgres_vector_search(query_vector, filters, top_k, provider, model, version, dimension)
        return self._sqlite_vector_search(query_vector, filters, top_k, provider, model, version, dimension)

    def keyword_search(self, query: str, filters: SearchFilterSet, top_k: int) -> list[dict]:
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            return self._postgres_keyword_search(query, filters, top_k)
        return self._sqlite_keyword_search(query, filters, top_k)

    def _postgres_vector_search(
        self,
        query_vector: list[float],
        filters: SearchFilterSet,
        top_k: int,
        provider: str,
        model: str,
        version: str,
        dimension: int,
    ) -> list[dict]:
        where_sql, params = self._postgres_filter_sql(filters)
        params.update(
            {
                "query_vector": "[" + ",".join(str(float(value)) for value in query_vector) + "]",
                "provider": provider,
                "model": model,
                "version": version,
                "dimension": dimension,
                "top_k": top_k,
            }
        )
        sql = text(
            f"""
            SELECT
                c.chunk_id::text,
                c.resource_id::text,
                c.chunk_index,
                c.chunk_text,
                c.page_start,
                c.page_end,
                c.section_title,
                c.heading_path,
                c.metadata_json AS chunk_metadata,
                r.title,
                r.metadata_json AS resource_metadata,
                1 - (e.vector <=> CAST(:query_vector AS vector)) AS vector_score
            FROM public.rag_chunk_embeddings e
            JOIN public.rag_document_chunks c ON c.chunk_id = e.chunk_id
            JOIN public.resources r ON r.resource_id = c.resource_id
            LEFT JOIN public.categories cat ON cat.category_id = r.category_id
            WHERE r.rag_enabled = true
              AND r.ingestion_status = 'READY'
              AND e.embedding_provider = :provider
              AND e.embedding_model = :model
              AND e.embedding_version = :version
              AND e.embedding_dimension = :dimension
              {where_sql}
            ORDER BY e.vector <=> CAST(:query_vector AS vector)
            LIMIT :top_k
            """
        )
        return [dict(row._mapping) for row in self.db.execute(sql, params)]

    def _postgres_keyword_search(self, query: str, filters: SearchFilterSet, top_k: int) -> list[dict]:
        where_sql, params = self._postgres_filter_sql(filters)
        params.update({"query": query, "top_k": top_k})
        sql = text(
            f"""
            WITH tag_matches AS (
                SELECT rt.resource_id, string_agg(t.tag_name, ' ') AS tag_text
                FROM public.resource_tags rt
                JOIN public.tags t ON t.tag_id = rt.tag_id
                GROUP BY rt.resource_id
            )
            SELECT
                c.chunk_id::text,
                c.resource_id::text,
                c.chunk_index,
                c.chunk_text,
                c.page_start,
                c.page_end,
                c.section_title,
                c.heading_path,
                c.metadata_json AS chunk_metadata,
                r.title,
                r.metadata_json AS resource_metadata,
                CASE
                    WHEN lower(r.title) = lower(:query) THEN 2
                    WHEN lower(r.title) LIKE '%' || lower(:query) || '%' THEN 1
                    ELSE 0
                END AS resource_match_score,
                (
                    ts_rank_cd(c.search_vector, websearch_to_tsquery('english', :query))
                    + CASE WHEN lower(r.title) = lower(:query) THEN 10.0 ELSE 0.0 END
                    + CASE WHEN lower(r.title) LIKE '%' || lower(:query) || '%' THEN 5.0 ELSE 0.0 END
                    + CASE WHEN lower(coalesce(r.metadata_json->>'author', '')) LIKE '%' || lower(:query) || '%' THEN 3.0 ELSE 0.0 END
                    + CASE WHEN lower(coalesce(cat.category_name, '')) LIKE '%' || lower(:query) || '%' THEN 2.0 ELSE 0.0 END
                    + CASE WHEN lower(coalesce(tm.tag_text, '')) LIKE '%' || lower(:query) || '%' THEN 2.0 ELSE 0.0 END
                    + CASE WHEN lower(c.chunk_text) LIKE '%' || lower(:query) || '%' THEN 1.0 ELSE 0.0 END
                ) AS keyword_score
            FROM public.rag_document_chunks c
            JOIN public.resources r ON r.resource_id = c.resource_id
            LEFT JOIN public.categories cat ON cat.category_id = r.category_id
            LEFT JOIN tag_matches tm ON tm.resource_id = r.resource_id
            WHERE r.rag_enabled = true
              AND r.ingestion_status = 'READY'
              AND (
                  c.search_vector @@ websearch_to_tsquery('english', :query)
                  OR lower(r.title) LIKE '%' || lower(:query) || '%'
                  OR lower(coalesce(r.metadata_json->>'author', '')) LIKE '%' || lower(:query) || '%'
                  OR lower(coalesce(cat.category_name, '')) LIKE '%' || lower(:query) || '%'
                  OR lower(coalesce(tm.tag_text, '')) LIKE '%' || lower(:query) || '%'
              )
              {where_sql}
            ORDER BY
                CASE
                    WHEN lower(r.title) = lower(:query) THEN 2
                    WHEN lower(r.title) LIKE '%' || lower(:query) || '%' THEN 1
                    ELSE 0
                END DESC,
                CASE
                    WHEN lower(r.title) = lower(:query)
                      OR lower(r.title) LIKE '%' || lower(:query) || '%'
                    THEN c.chunk_index
                    ELSE 0
                END ASC,
                keyword_score DESC,
                c.created_at DESC
            LIMIT :top_k
            """
        )
        return [dict(row._mapping) for row in self.db.execute(sql, params)]

    def _postgres_filter_sql(self, filters: SearchFilterSet) -> tuple[str, dict[str, Any]]:
        clauses: list[str] = []
        params: dict[str, Any] = {}
        if filters.resource_id:
            clauses.append("AND c.resource_id = CAST(:resource_id AS uuid)")
            params["resource_id"] = filters.resource_id
        if filters.category:
            clauses.append("AND cat.category_name = :category")
            params["category"] = filters.category
        if filters.tags:
            clauses.append(
                """
                AND EXISTS (
                    SELECT 1
                    FROM public.resource_tags rt
                    JOIN public.tags t ON t.tag_id = rt.tag_id
                    WHERE rt.resource_id = r.resource_id
                      AND t.tag_name = ANY(:tags)
                )
                """
            )
            params["tags"] = filters.tags
        if filters.metadata:
            clauses.append("AND r.metadata_json @> CAST(:metadata_json AS jsonb)")
            params["metadata_json"] = json.dumps(filters.metadata)
        return "\n".join(clauses), params

    def _base_sqlite_query(self, filters: SearchFilterSet):
        query = (
            self.db.query(RagDocumentChunk, Resource, Category)
            .join(Resource, Resource.resource_id == RagDocumentChunk.resource_id)
            .outerjoin(Category, Category.category_id == Resource.category_id)
            .filter(Resource.rag_enabled.is_(True), Resource.ingestion_status == "READY")
        )
        if filters.resource_id:
            query = query.filter(RagDocumentChunk.resource_id == filters.resource_id)
        if filters.category:
            query = query.filter(Category.category_name == filters.category)
        if filters.tags:
            query = (
                query.join(ResourceTag, ResourceTag.resource_id == Resource.resource_id)
                .join(Tag, Tag.tag_id == ResourceTag.tag_id)
                .filter(Tag.tag_name.in_(filters.tags))
            )
        return query

    def _sqlite_keyword_search(self, query_text: str, filters: SearchFilterSet, top_k: int) -> list[dict]:
        terms = tokenize_meaningful(query_text)
        query_counts = token_counts(query_text)
        if not terms:
            return []
        rows = []
        for chunk, resource, _category in self._base_sqlite_query(filters).all():
            text = chunk.chunk_text or ""
            title = resource.title or ""
            metadata = resource.resource_metadata or {}
            author = str(metadata.get("author") or "")
            description = str(metadata.get("description") or "")
            tags = " ".join(str(tag) for tag in metadata.get("tags") or [])
            category = str(metadata.get("category_name") or "")
            searchable_resource_text = " ".join([title, author, description, tags, category])

            text_counts = token_counts(text)
            title_counts = token_counts(title)
            resource_counts = token_counts(searchable_resource_text)

            score = 0.0
            score += sum(min(query_counts[term], text_counts.get(term, 0)) for term in query_counts)
            score += 4.0 * sum(min(query_counts[term], title_counts.get(term, 0)) for term in query_counts)
            score += 1.5 * sum(min(query_counts[term], resource_counts.get(term, 0)) for term in query_counts)

            exact_phrase_match = phrase_in_text(query_text, text)
            if phrase_in_text(query_text, text):
                score += 25.0
            if phrase_in_text(query_text, title):
                score += 40.0
            if phrase_in_text(query_text, searchable_resource_text):
                score += 10.0

            title_terms = set(title_counts)
            query_terms = set(query_counts)
            text_terms = set(text_counts)
            resource_terms = set(resource_counts)
            matched_terms = query_terms & (text_terms | resource_terms)
            if len(query_terms) >= 4 and len(matched_terms) / len(query_terms) < 0.20:
                continue
            title_overlap = len(title_terms & query_terms) / len(title_terms) if title_terms else 0.0
            query_overlap = len(title_terms & query_terms) / len(query_terms) if query_terms else 0.0
            if title_overlap == 1.0:
                score += 20.0
                resource_match_score = 2.0
            elif title_overlap >= 0.5 or query_overlap >= 0.5:
                score += 8.0
                resource_match_score = 1.0
            else:
                resource_match_score = 0.0

            if score > 0:
                rows.append(
                    self._row_dict(
                        chunk,
                        resource,
                        keyword_score=float(score),
                        resource_match_score=float(resource_match_score),
                        exact_phrase_match=exact_phrase_match,
                    )
                )

        def sort_key(item: dict) -> tuple[float, int, float]:
            resource_match = float(item.get("resource_match_score") or 0.0)
            chunk_index = int(item.get("chunk_index") or 0) if resource_match else 0
            return (-resource_match, chunk_index, -float(item["keyword_score"]))

        rows.sort(key=sort_key)
        return rows[:top_k]

    def _sqlite_vector_search(
        self,
        query_vector: list[float],
        filters: SearchFilterSet,
        top_k: int,
        provider: str,
        model: str,
        version: str,
        dimension: int,
    ) -> list[dict]:
        rows = (
            self._base_sqlite_query(filters)
            .join(RagChunkEmbedding, RagChunkEmbedding.chunk_id == RagDocumentChunk.chunk_id)
            .filter(
                RagChunkEmbedding.embedding_provider == provider,
                RagChunkEmbedding.embedding_model == model,
                RagChunkEmbedding.embedding_version == version,
                RagChunkEmbedding.embedding_dimension == dimension,
            )
            .all()
        )
        results = []
        embeddings = self.db.query(RagChunkEmbedding).all()
        embeddings_by_chunk = {embedding.chunk_id: embedding for embedding in embeddings}
        for chunk, resource, _category in rows:
            embedding = embeddings_by_chunk.get(chunk.chunk_id)
            score = _cosine_similarity(query_vector, embedding.vector if embedding else [])
            results.append(self._row_dict(chunk, resource, vector_score=score))
        results.sort(key=lambda item: item["vector_score"], reverse=True)
        return results[:top_k]

    def _row_dict(self, chunk: RagDocumentChunk, resource: Resource, **scores: float) -> dict:
        return {
            "chunk_id": chunk.chunk_id,
            "resource_id": chunk.resource_id,
            "chunk_index": chunk.chunk_index,
            "chunk_text": chunk.chunk_text,
            "page_start": chunk.page_start,
            "page_end": chunk.page_end,
            "section_title": chunk.section_title,
            "heading_path": chunk.heading_path or [],
            "chunk_metadata": chunk.chunk_metadata or {},
            "resource_metadata": resource.resource_metadata or {},
            "title": resource.title,
            **scores,
        }


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot = sum(a * b for a, b in zip(left, right, strict=False))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot / (left_norm * right_norm)
