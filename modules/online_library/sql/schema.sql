-- Online Library database schema snapshot.
-- Source database: postgresql://localhost:5432/online_library
-- Snapshot purpose: support planning for the modules/online_library FastAPI module.

CREATE TABLE public.authors (
    author_id uuid NOT NULL DEFAULT gen_random_uuid(),
    author_name character varying(200) NOT NULL,
    bio text,
    country character varying(100),
    status character varying(30) NOT NULL DEFAULT 'ACTIVE'::character varying,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT authors_pkey PRIMARY KEY (author_id),
    CONSTRAINT ux_authors_name UNIQUE (author_name)
);

CREATE TABLE public.categories (
    category_id uuid NOT NULL DEFAULT gen_random_uuid(),
    category_name character varying(200) NOT NULL,
    description text,
    status character varying(30) NOT NULL DEFAULT 'ACTIVE'::character varying,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT categories_pkey PRIMARY KEY (category_id),
    CONSTRAINT ux_categories_name UNIQUE (category_name)
);

CREATE TABLE public.subscription_tiers (
    tier_code character varying(30) NOT NULL,
    tier_name character varying(100) NOT NULL,
    description text,
    display_order integer NOT NULL,
    status character varying(30) NOT NULL DEFAULT 'ACTIVE'::character varying,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT subscription_tiers_pkey PRIMARY KEY (tier_code)
);

CREATE TABLE public.tags (
    tag_id uuid NOT NULL DEFAULT gen_random_uuid(),
    tag_name character varying(100) NOT NULL,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT tags_pkey PRIMARY KEY (tag_id),
    CONSTRAINT ux_tags_name UNIQUE (tag_name)
);

CREATE TABLE public.library_users (
    user_id uuid NOT NULL DEFAULT gen_random_uuid(),
    full_name character varying(200) NOT NULL,
    email character varying(320) NOT NULL,
    keycloak_user_id character varying(100),
    status character varying(50) NOT NULL DEFAULT 'PENDING_APPROVAL'::character varying,
    approval_status character varying(50) NOT NULL DEFAULT 'PENDING_APPROVAL'::character varying,
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
    title character varying(500) NOT NULL,
    resource_type character varying(50) NOT NULL,
    description text,
    category_id uuid,
    publisher character varying(200),
    published_date date,
    language character varying(80) NOT NULL DEFAULT 'English'::character varying,
    isbn character varying(50),
    page_count integer,
    file_url text,
    preview_file_url text,
    cover_image_url text,
    file_name character varying(500),
    file_content_type character varying(200),
    file_size_bytes bigint,
    file_content bytea,
    preview_file_name character varying(500),
    preview_content_type character varying(200),
    preview_size_bytes bigint,
    preview_content bytea,
    is_premium boolean NOT NULL DEFAULT false,
    minimum_tier_code character varying(30) NOT NULL DEFAULT 'FREE'::character varying,
    status character varying(30) NOT NULL DEFAULT 'ACTIVE'::character varying,
    created_by uuid,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT resources_pkey PRIMARY KEY (resource_id),
    CONSTRAINT resources_category_id_fkey FOREIGN KEY (category_id) REFERENCES public.categories(category_id),
    CONSTRAINT resources_created_by_fkey FOREIGN KEY (created_by) REFERENCES public.library_users(user_id),
    CONSTRAINT resources_minimum_tier_code_fkey FOREIGN KEY (minimum_tier_code) REFERENCES public.subscription_tiers(tier_code)
);

CREATE TABLE public.audit_log (
    audit_id uuid NOT NULL DEFAULT gen_random_uuid(),
    actor_user_id uuid,
    action character varying(100) NOT NULL,
    entity_type character varying(100),
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
    ip_address character varying(80),
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

CREATE TABLE public.reviews (
    review_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    rating integer,
    review_text text,
    status character varying(30) NOT NULL DEFAULT 'ACTIVE'::character varying,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT reviews_pkey PRIMARY KEY (review_id),
    CONSTRAINT ux_reviews_user_resource UNIQUE (user_id, resource_id),
    CONSTRAINT reviews_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT reviews_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.subscription_rules (
    rule_id uuid NOT NULL DEFAULT gen_random_uuid(),
    tier_code character varying(30) NOT NULL,
    rule_key character varying(100) NOT NULL,
    rule_value character varying(500) NOT NULL,
    data_type character varying(30),
    description text,
    status character varying(30) NOT NULL DEFAULT 'ACTIVE'::character varying,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT subscription_rules_pkey PRIMARY KEY (rule_id),
    CONSTRAINT ux_subscription_rules_tier_key UNIQUE (tier_code, rule_key),
    CONSTRAINT subscription_rules_tier_code_fkey FOREIGN KEY (tier_code) REFERENCES public.subscription_tiers(tier_code)
);

CREATE TABLE public.user_approval_requests (
    approval_request_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    request_status character varying(50) NOT NULL,
    reviewed_by uuid,
    reviewed_at timestamp without time zone,
    review_comments text,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT user_approval_requests_pkey PRIMARY KEY (approval_request_id),
    CONSTRAINT user_approval_requests_reviewed_by_fkey FOREIGN KEY (reviewed_by) REFERENCES public.library_users(user_id),
    CONSTRAINT user_approval_requests_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.user_bookshelf (
    bookshelf_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    resource_id uuid NOT NULL,
    status character varying(30) NOT NULL DEFAULT 'CHECKED_OUT'::character varying,
    checked_out_at timestamp without time zone,
    removed_at timestamp without time zone,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT user_bookshelf_pkey PRIMARY KEY (bookshelf_id),
    CONSTRAINT ux_user_bookshelf_user_resource UNIQUE (user_id, resource_id),
    CONSTRAINT user_bookshelf_resource_id_fkey FOREIGN KEY (resource_id) REFERENCES public.resources(resource_id),
    CONSTRAINT user_bookshelf_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.library_users(user_id)
);

CREATE TABLE public.user_subscriptions (
    subscription_id uuid NOT NULL DEFAULT gen_random_uuid(),
    user_id uuid NOT NULL,
    tier_code character varying(30) NOT NULL,
    start_date date NOT NULL DEFAULT CURRENT_DATE,
    end_date date,
    status character varying(30) NOT NULL DEFAULT 'ACTIVE'::character varying,
    created_at timestamp without time zone NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone,
    CONSTRAINT user_subscriptions_pkey PRIMARY KEY (subscription_id),
    CONSTRAINT user_subscriptions_tier_code_fkey FOREIGN KEY (tier_code) REFERENCES public.subscription_tiers(tier_code),
    CONSTRAINT user_subscriptions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.library_users(user_id)
);
