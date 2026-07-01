-- RAG ingestion service full base schema.
-- PostgreSQL schema for an empty database; no migration of existing data is required.

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE public.authors (
    author_id uuid NOT NULL DEFAULT gen_random_uuid(),
    author_name varchar(200) NOT NULL,
    bio text,
    country varchar(100),
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT authors_pkey PRIMARY KEY (author_id),
    CONSTRAINT ux_authors_name UNIQUE (author_name)
);

CREATE TABLE public.categories (
    category_id uuid NOT NULL DEFAULT gen_random_uuid(),
    category_name varchar(200) NOT NULL,
    description text,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT categories_pkey PRIMARY KEY (category_id),
    CONSTRAINT ux_categories_name UNIQUE (category_name)
);

CREATE TABLE public.subscription_tiers (
    tier_code varchar(30) NOT NULL,
    tier_name varchar(100) NOT NULL,
    description text,
    display_order integer NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT subscription_tiers_pkey PRIMARY KEY (tier_code)
);

INSERT INTO public.subscription_tiers (tier_code, tier_name, description, display_order)
VALUES ('FREE', 'Free', 'Default free access tier', 1)
ON CONFLICT (tier_code) DO NOTHING;

CREATE TABLE public.tags (
    tag_id uuid NOT NULL DEFAULT gen_random_uuid(),
    tag_name varchar(100) NOT NULL,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT tags_pkey PRIMARY KEY (tag_id),
    CONSTRAINT ux_tags_name UNIQUE (tag_name)
);

CREATE TABLE public.library_users (
    user_id uuid NOT NULL DEFAULT gen_random_uuid(),
    full_name varchar(200) NOT NULL,
    email varchar(320) NOT NULL,
    keycloak_user_id varchar(100),
    status varchar(50) NOT NULL DEFAULT 'PENDING_APPROVAL',
    approval_status varchar(50) NOT NULL DEFAULT 'PENDING_APPROVAL',
    approved_by uuid,
    approved_at timestamp without time zone,
    rejected_reason text,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT library_users_pkey PRIMARY KEY (user_id),
    CONSTRAINT library_users_approved_by_fkey FOREIGN KEY (approved_by) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.resources (
    resource_id uuid NOT NULL DEFAULT gen_random_uuid(),
    title varchar(500) NOT NULL,
    resource_type varchar(50) NOT NULL,
    description text,
    category_id uuid,
    publisher varchar(200),
    published_date date,
    language varchar(80) NOT NULL DEFAULT 'English',
    isbn varchar(50),
    page_count integer,
    file_url text,
    preview_file_url text,
    cover_image_url text,
    file_name varchar(500),
    file_content_type varchar(200),
    file_size_bytes bigint,
    file_content bytea,
    preview_file_name varchar(500),
    preview_content_type varchar(200),
    preview_size_bytes bigint,
    preview_content bytea,
    is_premium boolean NOT NULL DEFAULT false,
    minimum_tier_code varchar(30) NOT NULL DEFAULT 'FREE',
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_by uuid,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,

    source_system varchar(100),
    original_file_hash_sha256 varchar(64),
    extracted_text_hash_sha256 varchar(64),
    file_extension varchar(30),
    rag_enabled boolean NOT NULL DEFAULT false,
    ingestion_status varchar(30) NOT NULL DEFAULT 'NOT_INDEXED',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    storage_path text,
    parser_name varchar(100),
    embedding_provider varchar(50),
    embedding_model varchar(150),
    embedding_version varchar(50) DEFAULT 'v1',

    CONSTRAINT resources_pkey PRIMARY KEY (resource_id),
    CONSTRAINT resources_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id),
    CONSTRAINT resources_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.library_users(user_id),
    CONSTRAINT resources_minimum_tier_code_fkey FOREIGN KEY (minimum_tier_code) REFERENCES public.subscription_tiers(tier_code)
);

CREATE TABLE public.resource_authors (
    resource_id uuid NOT NULL,
    author_id uuid NOT NULL,
    CONSTRAINT resource_authors_pkey PRIMARY KEY (resource_id, author_id),
    CONSTRAINT resource_authors_author_id_fkey FOREIGN KEY (author_id) REFERENCES public.authors(author_id),
    CONSTRAINT resource_authors_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id)
);

CREATE TABLE public.resource_tags (
    resource_id uuid NOT NULL,
    tag_id uuid NOT NULL,
    CONSTRAINT resource_tags_pkey PRIMARY KEY (resource_id, tag_id),
    CONSTRAINT resource_tags_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT resource_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(tag_id)
);

CREATE TABLE public.user_approval_requests (
    approval_request_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    request_status varchar(50) NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp without time zone,
    review_comments text,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT user_approval_requests_pkey PRIMARY KEY (approval_request_id),
    CONSTRAINT user_approval_requests_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.library_users(user_id),
    CONSTRAINT user_approval_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.user_subscriptions (
    subscription_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    tier_code varchar(30) NOT NULL,
    start_date date NOT NULL DEFAULT CURRENT_DATE,
    end_date date,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT user_subscriptions_pkey PRIMARY KEY (subscription_id),
    CONSTRAINT user_subscriptions_tier_code_fkey FOREIGN KEY (tier_code) REFERENCES public.subscription_tiers(tier_code),
    CONSTRAINT user_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.subscription_rules (
    rule_id uuid NOT NULL DEFAULT gen_random_uuid(),
    tier_code varchar(30) NOT NULL,
    rule_key varchar(100) NOT NULL,
    rule_value varchar(500) NOT NULL,
    data_type varchar(30),
    description text,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT subscription_rules_pkey PRIMARY KEY (rule_id),
    CONSTRAINT ux_subscription_rules_tier_key UNIQUE (tier_code, rule_key),
    CONSTRAINT subscription_rules_tier_code_fkey FOREIGN KEY (tier_code) REFERENCES public.subscription_tiers(tier_code)
);

CREATE TABLE public.audit_log (
    audit_id uuid NOT NULL DEFAULT gen_random_uuid(),
    actor_user_id uuid,
    action varchar(100) NOT NULL,
    entity_type varchar(100),
    entity_id uuid,
    details text,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT audit_log_pkey PRIMARY KEY (audit_id),
    CONSTRAINT audit_log_actor_user_id_fkey FOREIGN KEY (actor_user_id) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.downloads (
    download_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    downloaded_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    ip_address varchar(80),
    user_agent text,
    CONSTRAINT downloads_pkey PRIMARY KEY (download_id),
    CONSTRAINT downloads_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT downloads_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.reading_progress (
    progress_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    current_page integer NOT NULL DEFAULT 0,
    progress_percent numeric(5,2) NOT NULL DEFAULT 0,
    last_read_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT reading_progress_pkey PRIMARY KEY (progress_id),
    CONSTRAINT ux_reading_progress_user_resource UNIQUE (user_id, resource_id),
    CONSTRAINT reading_progress_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT reading_progress_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.reviews (
    review_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    rating integer,
    review_text text,
    status varchar(30) NOT NULL DEFAULT 'ACTIVE',
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT reviews_pkey PRIMARY KEY (review_id),
    CONSTRAINT ux_reviews_user_resource UNIQUE (user_id, resource_id),
    CONSTRAINT reviews_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT reviews_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.user_bookshelf (
    bookshelf_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'CHECKED_OUT',
    checked_out_at timestamp without time zone,
    removed_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT user_bookshelf_pkey PRIMARY KEY (bookshelf_id),
    CONSTRAINT ux_user_bookshelf_user_resource UNIQUE (user_id, resource_id),
    CONSTRAINT user_bookshelf_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT user_bookshelf_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.rag_ingestion_jobs (
    job_id uuid NOT NULL DEFAULT gen_random_uuid(),
    resource_id uuid NOT NULL,
    status varchar(30) NOT NULL DEFAULT 'QUEUED',
    async_backend varchar(50) NOT NULL,
    chunking_strategy varchar(80) NOT NULL DEFAULT 'SEMANTIC_RECURSIVE',
    indexing_mode varchar(20) NOT NULL DEFAULT 'STANDARD',
    chunk_size_tokens integer NOT NULL DEFAULT 1200,
    chunk_overlap_tokens integer NOT NULL DEFAULT 80,
    total_chunks integer NOT NULL DEFAULT 0,
    processed_chunks integer NOT NULL DEFAULT 0,
    embedded_chunks integer NOT NULL DEFAULT 0,
    graph_entities_count integer NOT NULL DEFAULT 0,
    graph_relationships_count integer NOT NULL DEFAULT 0,
    failed_chunks integer NOT NULL DEFAULT 0,
    retry_count integer NOT NULL DEFAULT 0,
    max_retries integer NOT NULL DEFAULT 3,
    worker_id varchar(120),
    locked_at timestamp without time zone,
    heartbeat_at timestamp without time zone,
    next_retry_at timestamp without time zone,
    progress_message text,
    error_message text,
    started_at timestamp without time zone,
    completed_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT rag_ingestion_jobs_pkey PRIMARY KEY (job_id),
    CONSTRAINT rag_ingestion_jobs_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id)
);

CREATE TABLE public.rag_document_extractions (
    extraction_id uuid NOT NULL DEFAULT gen_random_uuid(),
    resource_id uuid NOT NULL,
    job_id uuid NOT NULL,
    parser_name varchar(100) NOT NULL,
    extracted_text text NOT NULL,
    extracted_text_hash_sha256 varchar(64) NOT NULL,
    page_count integer,
    char_count integer NOT NULL DEFAULT 0,
    token_count integer NOT NULL DEFAULT 0,
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rag_document_extractions_pkey PRIMARY KEY (extraction_id),
    CONSTRAINT rag_document_extractions_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT rag_document_extractions_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.rag_ingestion_jobs(job_id)
);

CREATE TABLE public.rag_document_chunks (
    chunk_id uuid NOT NULL DEFAULT gen_random_uuid(),
    resource_id uuid NOT NULL,
    job_id uuid NOT NULL,
    chunk_index integer NOT NULL,
    chunk_text text NOT NULL,
    chunk_hash_sha256 varchar(64) NOT NULL,
    token_count integer NOT NULL,
    char_count integer NOT NULL,
    page_start integer,
    page_end integer,
    section_title varchar(500),
    heading_path jsonb NOT NULL DEFAULT '[]'::jsonb,
    chunk_type varchar(50) NOT NULL DEFAULT 'text',
    metadata_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    search_vector tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(chunk_text, ''))) STORED,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rag_document_chunks_pkey PRIMARY KEY (chunk_id),
    CONSTRAINT rag_document_chunks_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT rag_document_chunks_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.rag_ingestion_jobs(job_id),
    CONSTRAINT ux_rag_chunks_resource_hash UNIQUE (resource_id, chunk_hash_sha256)
);

CREATE TABLE public.rag_chunk_embeddings (
    embedding_id uuid NOT NULL DEFAULT gen_random_uuid(),
    chunk_id uuid NOT NULL,
    embedding_provider varchar(50) NOT NULL,
    embedding_model varchar(150) NOT NULL,
    embedding_version varchar(50) NOT NULL DEFAULT 'v1',
    embedding_dimension integer NOT NULL,
    vector vector(768) NOT NULL,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rag_chunk_embeddings_pkey PRIMARY KEY (embedding_id),
    CONSTRAINT rag_chunk_embeddings_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.rag_document_chunks(chunk_id),
    CONSTRAINT ux_rag_embedding_version UNIQUE (chunk_id, embedding_provider, embedding_model, embedding_version)
);

CREATE TABLE public.rag_processing_errors (
    error_id uuid NOT NULL DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    chunk_id uuid,
    stage varchar(80) NOT NULL,
    error_type varchar(150) NOT NULL,
    error_message text NOT NULL,
    error_details jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rag_processing_errors_pkey PRIMARY KEY (error_id),
    CONSTRAINT rag_processing_errors_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.rag_ingestion_jobs(job_id),
    CONSTRAINT rag_processing_errors_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT rag_processing_errors_chunk_id_fkey FOREIGN KEY (chunk_id) REFERENCES public.rag_document_chunks(chunk_id)
);

CREATE TABLE public.rag_profiling_events (
    profile_event_id uuid NOT NULL DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    step varchar(120) NOT NULL,
    status varchar(30) NOT NULL,
    elapsed_ms double precision NOT NULL DEFAULT 0,
    event_index integer NOT NULL,
    details_json jsonb NOT NULL DEFAULT '{}'::jsonb,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rag_profiling_events_pkey PRIMARY KEY (profile_event_id),
    CONSTRAINT rag_profiling_events_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.rag_ingestion_jobs(job_id),
    CONSTRAINT rag_profiling_events_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id)
);

CREATE TABLE public.rag_graph_entities (
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

CREATE TABLE public.rag_graph_relationships (
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

CREATE TABLE public.rag_graph_communities (
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

CREATE TABLE public.rag_graph_entity_communities (
    id uuid NOT NULL DEFAULT gen_random_uuid(),
    entity_id uuid NOT NULL,
    community_id uuid NOT NULL,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT rag_graph_entity_communities_pkey PRIMARY KEY (id),
    CONSTRAINT ux_rag_graph_entity_community UNIQUE (entity_id, community_id),
    CONSTRAINT rag_graph_entity_communities_entity_id_fkey FOREIGN KEY (entity_id) REFERENCES public.rag_graph_entities(entity_id),
    CONSTRAINT rag_graph_entity_communities_community_id_fkey FOREIGN KEY (community_id) REFERENCES public.rag_graph_communities(community_id)
);

CREATE TABLE public.rag_graph_summaries (
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

CREATE INDEX ix_resources_rag_enabled ON public.resources (rag_enabled);
CREATE INDEX ix_resources_ingestion_status ON public.resources (ingestion_status);
CREATE INDEX ix_resources_original_file_hash ON public.resources (original_file_hash_sha256);
CREATE INDEX ix_resources_metadata_json ON public.resources USING gin (metadata_json);
CREATE INDEX ix_resources_title ON public.resources (title);
CREATE INDEX ix_resources_publisher ON public.resources (publisher);
CREATE INDEX ix_resources_isbn ON public.resources (isbn);
CREATE INDEX ix_resources_published_date ON public.resources (published_date);
CREATE INDEX ix_authors_author_name ON public.authors (author_name);
CREATE INDEX ix_categories_category_name ON public.categories (category_name);
CREATE INDEX ix_tags_tag_name ON public.tags (tag_name);
CREATE INDEX ix_rag_jobs_status_created ON public.rag_ingestion_jobs (status, created_at);
CREATE INDEX ix_rag_jobs_resource_id ON public.rag_ingestion_jobs (resource_id);
CREATE INDEX ix_rag_jobs_worker_id ON public.rag_ingestion_jobs (worker_id);
CREATE INDEX ix_rag_jobs_next_retry_at ON public.rag_ingestion_jobs (next_retry_at);
CREATE INDEX ix_rag_chunks_resource_id ON public.rag_document_chunks (resource_id);
CREATE INDEX ix_rag_chunks_job_id ON public.rag_document_chunks (job_id);
CREATE INDEX ix_rag_chunks_text_trgm ON public.rag_document_chunks USING gin (chunk_text gin_trgm_ops);
CREATE INDEX ix_rag_document_chunks_search_vector ON public.rag_document_chunks USING gin (search_vector);
CREATE INDEX ix_rag_document_chunks_resource_page ON public.rag_document_chunks (resource_id, page_start, page_end);
CREATE INDEX ix_rag_embeddings_chunk_id ON public.rag_chunk_embeddings (chunk_id);
CREATE INDEX ix_rag_chunk_embeddings_model_lookup ON public.rag_chunk_embeddings (embedding_provider, embedding_model, embedding_version, embedding_dimension);
CREATE INDEX ix_rag_errors_job_id ON public.rag_processing_errors (job_id);
CREATE INDEX ix_rag_profile_events_job_id ON public.rag_profiling_events (job_id, event_index);
CREATE INDEX ix_rag_profile_events_resource_id ON public.rag_profiling_events (resource_id);
CREATE INDEX ix_rag_graph_entities_resource_id ON public.rag_graph_entities (resource_id);
CREATE INDEX ix_rag_graph_entities_chunk_id ON public.rag_graph_entities (chunk_id);
CREATE INDEX ix_rag_graph_entities_normalized_name ON public.rag_graph_entities (normalized_name);
CREATE INDEX ix_rag_graph_entities_entity_type ON public.rag_graph_entities (entity_type);
CREATE INDEX ix_rag_graph_entities_name_trgm ON public.rag_graph_entities USING gin (name gin_trgm_ops);
CREATE INDEX ix_rag_graph_relationships_resource_id ON public.rag_graph_relationships (resource_id);
CREATE INDEX ix_rag_graph_relationships_chunk_id ON public.rag_graph_relationships (chunk_id);
CREATE INDEX ix_rag_graph_relationships_source_entity_id ON public.rag_graph_relationships (source_entity_id);
CREATE INDEX ix_rag_graph_relationships_target_entity_id ON public.rag_graph_relationships (target_entity_id);
CREATE INDEX ix_rag_graph_relationships_type ON public.rag_graph_relationships (relationship_type);
CREATE INDEX ix_rag_graph_relationships_description_trgm ON public.rag_graph_relationships USING gin (description gin_trgm_ops);
CREATE INDEX ix_rag_graph_communities_resource_id ON public.rag_graph_communities (resource_id);
CREATE INDEX ix_rag_graph_entity_communities_entity_id ON public.rag_graph_entity_communities (entity_id);
CREATE INDEX ix_rag_graph_entity_communities_community_id ON public.rag_graph_entity_communities (community_id);
CREATE INDEX ix_rag_graph_summaries_resource_id ON public.rag_graph_summaries (resource_id);
CREATE INDEX ix_rag_graph_summaries_type ON public.rag_graph_summaries (summary_type);

-- For production vector search, choose an index after confirming dimensions and distance metric:
CREATE INDEX ix_rag_chunk_embeddings_vector_hnsw ON public.rag_chunk_embeddings USING hnsw (vector vector_cosine_ops);
