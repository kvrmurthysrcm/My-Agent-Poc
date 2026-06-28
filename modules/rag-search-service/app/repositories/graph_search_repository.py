from sqlalchemy import bindparam, text
from sqlalchemy.orm import Session


class GraphSearchRepository:
    def __init__(self, db: Session):
        self.db = db

    def search_entities(self, query: str, resource_ids: list[str], top_k: int) -> list[dict]:
        resource_filter, params = self._resource_filter("e", resource_ids)
        params.update({"query": query, "top_k": top_k})
        sql = text(
            f"""
            SELECT
                e.entity_id::text,
                e.resource_id::text,
                e.name,
                e.normalized_name,
                e.entity_type,
                e.description,
                e.confidence_score,
                e.metadata_json AS metadata,
                r.title AS resource_title,
                GREATEST(
                    similarity(e.name, :query),
                    similarity(e.normalized_name, lower(:query)),
                    CASE WHEN lower(e.name) LIKE '%' || lower(:query) || '%' THEN 1 ELSE 0 END
                ) AS score
            FROM public.rag_graph_entities e
            JOIN public.resources r ON r.resource_id = e.resource_id
            WHERE r.ingestion_status = 'READY'
              AND (
                lower(e.name) LIKE '%' || lower(:query) || '%'
                OR lower(e.normalized_name) LIKE '%' || lower(:query) || '%'
                OR similarity(e.name, :query) > 0.1
                OR similarity(e.normalized_name, lower(:query)) > 0.1
              )
              {resource_filter}
            ORDER BY score DESC, e.created_at DESC
            LIMIT :top_k
            """
        )
        sql = _bind_expanding(sql, resource_ids=bool(resource_ids))
        return [dict(row._mapping) for row in self.db.execute(sql, params)]

    def search_relationships(self, query: str, resource_ids: list[str], top_k: int) -> list[dict]:
        resource_filter, params = self._resource_filter("rel", resource_ids)
        params.update({"query": query, "top_k": top_k})
        sql = text(
            f"""
            SELECT
                rel.relationship_id::text,
                rel.resource_id::text,
                rel.source_entity_id::text,
                src.name AS source_entity_name,
                rel.target_entity_id::text,
                tgt.name AS target_entity_name,
                rel.relationship_type,
                rel.description,
                rel.confidence_score,
                rel.metadata_json AS metadata,
                r.title AS resource_title,
                GREATEST(
                    similarity(coalesce(rel.description, ''), :query),
                    similarity(rel.relationship_type, upper(:query)),
                    CASE WHEN lower(coalesce(rel.description, '')) LIKE '%' || lower(:query) || '%' THEN 1 ELSE 0 END,
                    CASE WHEN lower(src.name) LIKE '%' || lower(:query) || '%' THEN 0.8 ELSE 0 END,
                    CASE WHEN lower(tgt.name) LIKE '%' || lower(:query) || '%' THEN 0.8 ELSE 0 END
                ) AS score
            FROM public.rag_graph_relationships rel
            JOIN public.rag_graph_entities src ON src.entity_id = rel.source_entity_id
            JOIN public.rag_graph_entities tgt ON tgt.entity_id = rel.target_entity_id
            JOIN public.resources r ON r.resource_id = rel.resource_id
            WHERE r.ingestion_status = 'READY'
              AND (
                lower(coalesce(rel.description, '')) LIKE '%' || lower(:query) || '%'
                OR lower(rel.relationship_type) LIKE '%' || lower(:query) || '%'
                OR lower(src.name) LIKE '%' || lower(:query) || '%'
                OR lower(tgt.name) LIKE '%' || lower(:query) || '%'
                OR similarity(coalesce(rel.description, ''), :query) > 0.1
              )
              {resource_filter}
            ORDER BY score DESC, rel.created_at DESC
            LIMIT :top_k
            """
        )
        sql = _bind_expanding(sql, resource_ids=bool(resource_ids))
        return [dict(row._mapping) for row in self.db.execute(sql, params)]

    def search_summaries(self, query: str, resource_ids: list[str], top_k: int) -> list[dict]:
        resource_filter, params = self._resource_filter("s", resource_ids)
        params.update({"query": query, "top_k": top_k})
        sql = text(
            f"""
            SELECT
                s.summary_id::text,
                s.resource_id::text,
                s.summary_type,
                s.summary_text,
                s.metadata_json AS metadata,
                r.title AS resource_title
            FROM public.rag_graph_summaries s
            JOIN public.resources r ON r.resource_id = s.resource_id
            WHERE r.ingestion_status = 'READY'
              AND (
                lower(s.summary_text) LIKE '%' || lower(:query) || '%'
                OR similarity(s.summary_text, :query) > 0.1
              )
              {resource_filter}
            ORDER BY similarity(s.summary_text, :query) DESC, s.created_at DESC
            LIMIT :top_k
            """
        )
        sql = _bind_expanding(sql, resource_ids=bool(resource_ids))
        return [dict(row._mapping) for row in self.db.execute(sql, params)]

    def related_chunks(self, resource_ids: list[str], chunk_ids: list[str], top_k: int) -> list[dict]:
        if not chunk_ids and not resource_ids:
            return []
        clauses = []
        params: dict = {"top_k": top_k}
        if chunk_ids:
            clauses.append("c.chunk_id IN :chunk_ids")
            params["chunk_ids"] = chunk_ids
        if resource_ids:
            clauses.append("c.resource_id IN :resource_ids")
            params["resource_ids"] = resource_ids
        sql = text(
            f"""
            SELECT
                c.chunk_id::text,
                c.resource_id::text,
                c.chunk_index,
                left(c.chunk_text, 700) AS snippet,
                r.title AS resource_title
            FROM public.rag_document_chunks c
            JOIN public.resources r ON r.resource_id = c.resource_id
            WHERE {' OR '.join(clauses)}
            ORDER BY c.chunk_index
            LIMIT :top_k
            """
        )
        sql = _bind_expanding(sql, chunk_ids=bool(chunk_ids), resource_ids=bool(resource_ids))
        return [dict(row._mapping) for row in self.db.execute(sql, params)]

    def _resource_filter(self, alias: str, resource_ids: list[str]) -> tuple[str, dict]:
        if not resource_ids:
            return "", {}
        return f"AND {alias}.resource_id IN :resource_ids", {"resource_ids": resource_ids}


def _bind_expanding(statement, resource_ids: bool = False, chunk_ids: bool = False):
    bindparams = []
    if resource_ids:
        bindparams.append(bindparam("resource_ids", expanding=True))
    if chunk_ids:
        bindparams.append(bindparam("chunk_ids", expanding=True))
    return statement.bindparams(*bindparams) if bindparams else statement
