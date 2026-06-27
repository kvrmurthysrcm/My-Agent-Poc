import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.db.models import Category
from app.search.filters import SearchFilterSet


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
        raise RuntimeError("RAG search requires PostgreSQL with pgvector")

    def keyword_search(
        self,
        query: str,
        filters: SearchFilterSet,
        top_k: int,
        query_intent: str | None = None,
    ) -> list[dict]:
        if self.db.bind and self.db.bind.dialect.name == "postgresql":
            return self._postgres_keyword_search(query, filters, top_k, query_intent)
        raise RuntimeError("RAG keyword search requires PostgreSQL full-text search")

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

    def _postgres_keyword_search(
        self,
        query: str,
        filters: SearchFilterSet,
        top_k: int,
        query_intent: str | None = None,
    ) -> list[dict]:
        where_sql, params = self._postgres_filter_sql(filters)
        params.update({"query": query, "top_k": top_k, "query_intent": query_intent or ""})
        sql = text(
            f"""
            WITH search_query AS (
                SELECT CASE
                    WHEN :query_intent = 'exact_quote' THEN phraseto_tsquery('english', :query)
                    ELSE websearch_to_tsquery('english', :query)
                END AS tsq
            ),
            tag_matches AS (
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
                    ts_rank_cd(c.search_vector, sq.tsq)
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
            CROSS JOIN search_query sq
            WHERE r.rag_enabled = true
              AND r.ingestion_status = 'READY'
              AND (
                  c.search_vector @@ sq.tsq
                  OR (:query_intent = 'exact_quote' AND lower(c.chunk_text) LIKE '%' || lower(:query) || '%')
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
