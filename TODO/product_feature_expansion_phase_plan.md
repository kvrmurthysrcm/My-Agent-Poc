# Product Feature Expansion Phase Plan

Current working baseline:

- Secure API gateway authenticates against Keycloak.
- Online library DB query API is working.
- Online library agent and MCP use the online library tools.
- RAG ingest, search, and answer services are working.
- Gateway UI already supports login, RAG book listing, ingest, content search, answer, compare, library search, and library tools.

## Key Findings

- The gateway can create Keycloak users automatically, but it needs a Keycloak admin-capable service account/client. The existing password-grant client is not enough by itself.
- The RAG ingest schema already has strong catalog structures: `resources`, `authors`, `categories`, `tags`, `resource_authors`, `resource_tags`, `library_users`, `subscription_tiers`, and `user_subscriptions`.
- RAG ingest already writes many normalized metadata fields, including title, author, category, publisher, published date, language, tags, and file metadata.
- The next work should formalize metadata persistence and catalog search APIs instead of redesigning the database.
- The current online library API is mostly generic read-only table exposure. Product-level catalog search needs dedicated domain endpoints.

## Phase 1: Registration and Auto Keycloak User Creation

Goal: users can register from the secure gateway login screen and immediately log in.

Implementation decision:

- Self-registration does not expose role selection to the public user.
- The gateway automatically assigns safe default roles:
  - `rag_user`
  - `rag_search_user`
- Admin role management should be implemented as a separate authenticated admin feature.
- The live library DB currently does not contain a role reference table, so role synchronization is Keycloak-first for Phase 1.
- Before admin role management is added, introduce explicit library role tables such as `application_roles` and `library_user_roles`, then synchronize those records with Keycloak realm roles.

Scope:

- Add a `Register` link/form to the gateway login UI.
- Add `POST /auth/register` in the secure gateway.
- Add registration schemas for:
  - full name
  - email
  - username
  - password
  - subscription tier
  - optional organization/phone later if needed
- Add a `KeycloakAdminClient` in the secure gateway.
- Use Keycloak Admin REST to:
  - create the user
  - enable the user
  - set the password
  - assign a default role, probably `rag_user`
- Save the user in `library_users`.
- Auto approve for now:
  - `status = ACTIVE`
  - `approval_status = APPROVED`
  - `approved_at = now`
- Save the selected tier in `user_subscriptions`.
- Add duplicate checks for username and email.

Implemented notes:

- Added Keycloak admin service-account client setup in `scripts/keycloak/01-keycloak-setup.ps1`.
- Added secure gateway registration endpoints:
  - `GET /auth/register/options`
  - `POST /auth/register`
- Added library persistence for approved user registration and active subscription creation.
- Added rollback: if library persistence fails after Keycloak user creation, the newly created Keycloak user is deleted.
- Added gateway UI registration form in the login screen.

Keycloak setup requirement:

- Create/configure a confidential admin client, for example `secure-gateway-admin`.
- Enable service accounts.
- Assign only the needed realm-management permissions:
  - `manage-users`
  - `view-users`
  - role mapping permission if assigning roles through the API

Tests:

- Register a valid user.
- Duplicate username/email is rejected cleanly.
- New user exists in Keycloak.
- New user exists in `library_users`.
- New subscription exists in `user_subscriptions`.
- New user can log in through the gateway.

## Phase 2: HTTPS on Existing Ports

Goal: keep the same service ports but serve HTTPS.

Target ports:

- Secure gateway: `8010`
- RAG ingest: `8000`
- RAG search: `8001`
- RAG answer: `8002`
- Online library MCP: `8004`
- Online library agent: `8005`

Recommended rollout:

1. Enable HTTPS for the secure gateway only.
2. Enable HTTPS for all FastAPI services.
3. Optionally enable HTTPS for Keycloak.

Implementation:

- Generate a local dev certificate and key.
- Update each service run script to pass uvicorn SSL arguments:
  - `--ssl-certfile`
  - `--ssl-keyfile`
- Update gateway downstream URLs from `http://localhost:<port>` to `https://localhost:<port>`.
- Update CORS origins to include HTTPS origins.
- Keep Keycloak HTTP initially if needed; gateway-to-Keycloak communication is server-side.

Caution:

- If services call each other with self-signed HTTPS, `httpx` may reject the certificate.
- Prefer trusting a local dev CA certificate.
- If needed for local POC only, use explicit dev-only certificate verification configuration. Do not hide this inside production defaults.

Tests:

- `https://localhost:8010/ui` loads.
- Login still works.
- RAG ingest through the gateway works.
- RAG search through the gateway works.
- RAG answer through the gateway works.
- Library search/tools through the gateway work.

## Phase 3: Dedicated Metadata Persistence During Ingest

Goal: ensure book/document metadata is searchable from real columns and joins, not only from JSON metadata.

Current useful persistence:

- `resources.title`
- `resources.description`
- `resources.resource_type`
- `resources.publisher`
- `resources.published_date`
- `resources.language`
- `resources.file_name`
- `resources.file_size_bytes`
- `resources.metadata_json`
- `authors`
- `categories`
- `tags`
- `resource_authors`
- `resource_tags`

Implementation:

- Add a focused service file:
  - `modules/rag-ingest-service/app/services/library_metadata_persistence_service.py`
- Centralize metadata mapping logic for:
  - normalized author names
  - category/genre handling
  - tag normalization
  - publisher/date/language mapping
  - raw metadata preservation
- Call this service from `IngestService.create_resource_and_job`.
- Keep full request and extracted file metadata in `metadata_json`.
- Keep structured searchable values in columns and join tables.

Genre handling recommendation:

- For now, treat `genre` as an alias of `category_name`.
- Use tags for multi-value topics.
- Add a dedicated `genres` table only if the product later needs a hard distinction between category and genre.

Suggested indexes:

- `resources.title`
- `resources.publisher`
- `resources.isbn`
- `resources.published_date`
- `authors.author_name`
- `categories.category_name`
- `tags.tag_name`
- Optional trigram indexes for partial search over title, author, category, and tag names.

Tests:

- Upload PDF with metadata.
- Upload DOCX with metadata.
- Upload EPUB with metadata.
- Confirm `resources` columns are populated.
- Confirm author/category/tag join rows are created.
- Confirm raw file metadata remains in `metadata_json`.
- Confirm duplicate-document behavior remains unchanged.

## Phase 4: Online Library Catalog Search API

Goal: search the online library catalog by structured fields such as author, genre/category, tag, publisher, language, tier, and status.

Recommendation:

- Implement catalog search in `online_library` first because it owns library/catalog data.
- Keep RAG search focused on content/chunk search.

New endpoints:

- `GET /catalog/resources`
- `GET /catalog/resources/{resource_id}`
- `GET /catalog/facets`
- Optional later: `POST /catalog/search` for richer filter payloads.

Supported filters:

- `q`
- `author`
- `category`
- `genre`
- `tag`
- `publisher`
- `language`
- `tier`
- `status`
- `published_from`
- `published_to`
- `limit`
- `offset`
- `sort`

Response fields:

- `resource_id`
- `title`
- `description`
- `authors`
- `category`
- `tags`
- `publisher`
- `published_date`
- `language`
- `isbn`
- `page_count`
- `is_premium`
- `minimum_tier_code`
- `status`
- `ingestion_status` if using the RAG-enriched schema

Tests:

- Search by title.
- Search by author.
- Search by category/genre.
- Search by tag.
- Search by publisher.
- Search with combined filters.
- Pagination works.
- Empty result responses are clean.

## Phase 5: Gateway Routes and Library View UI

Goal: users and admins can browse the online library catalog through the secure gateway UI.

Gateway routes:

- `GET /library/catalog/resources`
- `GET /library/catalog/resources/{resource_id}`
- `GET /library/catalog/facets`

UI changes:

- Add a `Library` nav item separate from the current `Books` view.
- Keep `Books` focused on RAG ingestion/admin status.
- Make `Library` the user-facing catalog browse/search view.

Library UI capabilities:

- Search box.
- Author filter.
- Category/genre filter.
- Tag filter.
- Tier/status filter.
- Dense table or list layout.
- Resource detail panel.
- Admin-only technical fields:
  - `resource_id`
  - ingestion status
  - file metadata
  - indexing state

Tests:

- Normal user can browse the library.
- Admin can see extra fields.
- Filters work without page reload.
- Existing RAG search still works.
- Existing library agent search still works.
- Existing library tools UI still works.

## Phase 6: MCP and Agent Catalog-Aware Search

Goal: natural-language library search should use richer catalog tools instead of only generic table tools.

Add MCP tools:

- `search_catalog_resources`
- `get_catalog_facets`
- `get_resource_detail`

Update agent planner hints:

- author/writer questions select `search_catalog_resources`
- genre/category questions select `search_catalog_resources`
- premium/free/tier questions select `search_catalog_resources`
- title/book/resource questions select `search_catalog_resources`

Tests:

- "Show books by X author."
- "Find free books in machine learning."
- "List books tagged python."
- "Show premium books in fiction."
- Verify the selected MCP tool is the catalog search tool.

## Recommended Delivery Order

1. Registration and Keycloak auto-create.
2. HTTPS gateway only, then all services after gateway is stable.
3. Metadata persistence cleanup during ingest.
4. Catalog search API.
5. Gateway library UI.
6. MCP/agent catalog-aware search.

This order keeps identity, transport, ingestion, catalog search, UI, and agent behavior independently testable.
