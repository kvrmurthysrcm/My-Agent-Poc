-- Graph RAG PostgreSQL/pgvector schema additions for the POC.
-- Use this only if applying graph tables to an existing local POC database.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

ALTER TABLE public.rag_ingestion_jobs
    ADD COLUMN IF NOT EXISTS indexing_mode varchar(20) NOT NULL DEFAULT 'STANDARD',
    ADD COLUMN IF NOT EXISTS graph_entities_count integer NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS graph_relationships_count integer NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS public.rag_graph_entities (
    entity_id uuid NOT NULL DEFAULT gen_random_uuid(),
    resource_id uuid NOT NULL,
    chunk_id uuid,
    name varchar(500) NOT NULL,
    normalized_name varchar(500) NOT NULL,
    entity_type varchar(120) NOT NULL DEFAULT 'UNKNOWN',
    description text,
    confidence_score double precision,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT rag_graph_entities_pkey PRIMARY KEY (entity_id),
    CONSTRAINT ux_rag_graph_entity_resource_name UNIQUE (resource_id, normalized_name),
    CONSTRAINT rag_graph_entities_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT rag_graph_entities_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.rag_document_chunks(chunk_id)
);

CREATE TABLE IF NOT EXISTS public.rag_graph_relationships (
    relationship_id uuid NOT NULL DEFAULT gen_random_uuid(),
    resource_id uuid NOT NULL,
    source_entity_id uuid NOT NULL,
    target_entity_id uuid NOT NULL,
    relationship_type varchar(160) NOT NULL DEFAULT 'RELATED_TO',
    description text,
    confidence_score double precision,
    chunk_id uuid,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT rag_graph_relationships_pkey PRIMARY KEY (relationship_id),
    CONSTRAINT rag_graph_relationships_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT rag_graph_relationships_source_entity_id_fkey FOREIGN KEY (source_entity_id) REFERENCES public.rag_graph_entities(entity_id),
    CONSTRAINT rag_graph_relationships_target_entity_id_fkey FOREIGN KEY (target_entity_id) REFERENCES public.rag_graph_entities(entity_id),
    CONSTRAINT rag_graph_relationships_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.rag_document_chunks(chunk_id)
);

CREATE TABLE IF NOT EXISTS public.rag_graph_communities (
    community_id uuid NOT NULL DEFAULT gen_random_uuid(),
    resource_id uuid NOT NULL,
    name varchar(300) NOT NULL,
    summary text,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT rag_graph_communities_pkey PRIMARY KEY (community_id),
    CONSTRAINT rag_graph_communities_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id)
);

CREATE TABLE IF NOT EXISTS public.rag_graph_entity_communities (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    entity_id uuid NOT NULL,
    community_id uuid NOT NULL,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rag_graph_entity_communities_pkey PRIMARY KEY (id),
    CONSTRAINT ux_rag_graph_entity_community UNIQUE (entity_id, community_id),
    CONSTRAINT rag_graph_entity_communities_entity_id_fkey FOREIGN KEY (entity_id) REFERENCES public.rag_graph_entities(entity_id),
    CONSTRAINT rag_graph_entity_communities_community_id_fkey FOREIGN KEY (community_id) REFERENCES public.rag_graph_communities(community_id)
);

CREATE TABLE IF NOT EXISTS public.rag_graph_summaries (
    summary_id uuid NOT NULL DEFAULT gen_random_uuid(),
    resource_id uuid NOT NULL,
    summary_type varchar(80) NOT NULL,
    summary_text text NOT NULL,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT rag_graph_summaries_pkey PRIMARY KEY (summary_id),
    CONSTRAINT rag_graph_summaries_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id)
);

CREATE INDEX IF NOT EXISTS ix_rag_graph_entities_resource_id ON public.rag_graph_entities (resource_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entities_chunk_id ON public.rag_graph_entities (chunk_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entities_normalized_name ON public.rag_graph_entities (normalized_name);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entities_entity_type ON public.rag_graph_entities (entity_type);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entities_name_trgm ON public.rag_graph_entities USING gin (name gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_rag_graph_relationships_resource_id ON public.rag_graph_relationships (resource_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_relationships_chunk_id ON public.rag_graph_relationships (chunk_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_relationships_source_entity_id ON public.rag_graph_relationships (source_entity_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_relationships_target_entity_id ON public.rag_graph_relationships (target_entity_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_relationships_type ON public.rag_graph_relationships (relationship_type);
CREATE INDEX IF NOT EXISTS ix_rag_graph_relationships_description_trgm ON public.rag_graph_relationships USING gin (description gin_trgm_ops);
CREATE INDEX IF NOT EXISTS ix_rag_graph_communities_resource_id ON public.rag_graph_communities (resource_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entity_communities_entity_id ON public.rag_graph_entity_communities (entity_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_entity_communities_community_id ON public.rag_graph_entity_communities (community_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_summaries_resource_id ON public.rag_graph_summaries (resource_id);
CREATE INDEX IF NOT EXISTS ix_rag_graph_summaries_type ON public.rag_graph_summaries (summary_type);
