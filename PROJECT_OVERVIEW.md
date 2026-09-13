# My Agent POC — Project Overview

## 1. Project Summary

My Agent POC is a Python-based collection of agent, Retrieval-Augmented Generation (RAG), and online-library services. Its main application is a secure, browser-accessible library platform where authenticated users can discover books, search indexed document content, and ask grounded questions. Administrators can upload documents, monitor ingestion, create vector or graph indexes, retry failed jobs, and remove resources.

The repository also contains two standalone weather-agent demonstrations that show deterministic tool use and LLM-assisted summarization.

The project is a proof of concept rather than a single deployable application. Each major capability is implemented as a separate service and can be started independently.

## 2. Overall Features

- Keycloak login, registration, token refresh, logout, and JWT validation.
- Role-based access for ordinary users, search users, ingest users, and administrators.
- A unified secure browser UI for catalog browsing, content search, grounded answers, model comparison, ingestion, and administration.
- Upload and extraction of TXT, PDF, DOCX, and EPUB documents.
- Configurable semantic or recursive document chunking and chunk-quality filtering.
- Standard vector RAG, Graph RAG, or combined indexing.
- OpenAI or local Ollama embedding support.
- Lexical, vector, hybrid, graph, and combined search workflows.
- Reciprocal-rank fusion, reranking, result-quality checks, query preprocessing, filters, and source snippets.
- Grounded answer generation with citations, faithfulness validation, and multiple LLM providers.
- Side-by-side model answer comparison, including Server-Sent Events streaming.
- Structured online-library catalog, author, user, subscription, and approval searches.
- MCP tools and a natural-language query agent for library data.
- Trace and request identifiers propagated across service boundaries.
- Health/readiness endpoints, Postman collections, test suites, and local startup scripts.

## 3. High-Level Architecture

```text
Browser
   |
   v
Secure API Gateway :8010 <----> Keycloak :8080
   |
   +----> RAG Ingest Service :8000 ----> PostgreSQL + pgvector
   |
   +----> RAG Search Service :8001 ----> PostgreSQL + pgvector
   |
   +----> RAG Answer Service :8002 ----> Search Service + LLM
   |
   +----> Online Library API :8003 ----> PostgreSQL
   |
   +----> Online Library MCP :8004 ----> Online Library API
   |
   +----> Online Library Agent :8005 --> MCP + Ollama
```

The browser normally communicates only with the Secure API Gateway. The gateway validates the user's Keycloak token, checks roles, forwards requests to the appropriate internal service, adds the internal API key and user headers, and propagates tracing headers.

## 4. Module-Level Details

### 4.1 `modules/secure_api` — Secure API Gateway and Main UI

**Purpose:** Provides the main application entry point, authentication boundary, authorization checks, downstream routing, and unified UI.

**What it does:**

- Authenticates users through Keycloak.
- supports registration, login, refresh, logout, and current-user lookup.
- Validates JWT signatures with cached Keycloak JWKS data.
- Extracts realm/client roles and applies endpoint-specific role requirements.
- Proxies RAG, catalog, library-search, and MCP-tool requests.
- Adds internal `X-API-Key` and user-context headers to downstream calls.
- Creates or forwards `traceparent`, `X-Trace-Id`, `X-Span-Id`, and request IDs.
- Produces consistent JSON errors, request logs, CORS handling, and health information.

**Main UI (`/ui`, port 8010):**

- Login and registration screens.
- Books dashboard with ingestion state, chunk/index information, refresh, selection, and admin actions.
- Library catalog filters and resource detail view.
- Content Search form and ranked result display.
- Answer form for grounded question answering.
- Compare view for running a question against multiple models.
- Natural-language Library Search.
- Admin-only Ingest form.
- Admin-only delete, retry, standard-embedding, Graph RAG indexing, and raw Library Tools controls.
- Dark/light theme persisted in browser storage.

The local POC stores access and refresh tokens in `localStorage`. Admin UI controls are shown only to users with `rag_admin` or `system_admin`; backend authorization remains authoritative.

### 4.2 `modules/rag-ingest-service` — Document Ingestion and Indexing

**Purpose:** Accepts documents and transforms them into searchable RAG data.

**What it does:**

- Validates and stores TXT, PDF, DOCX, and EPUB uploads.
- Extracts embedded metadata and text using format-specific parsers.
- Merges submitted metadata with document metadata, with request values taking precedence.
- Cleans PDF text, inserts page markers, calculates hashes, and detects duplicates/invalid input.
- Splits text with semantic-recursive or intelligent-recursive chunking.
- Labels or excludes boilerplate, front matter, tables of contents, and low-quality chunks.
- Generates embeddings through OpenAI or Ollama.
- Builds Graph RAG entities, relationships, and summaries when requested.
- Supports `NONE`, `STANDARD`, `GRAPH`, and `BOTH` indexing modes.
- Records jobs, profiling events, processing errors, extraction data, chunks, and embeddings.
- Dispatches work through FastAPI background tasks, a database worker, RQ, or Kafka, depending on configuration.
- Recovers stale processing jobs and supports retry or later indexing of existing resources.

**Standalone UI (`/ui`, port 8000):** Upload form, metadata editor/preview, indexing-mode and chunking controls, job status, and polling until completion or failure.

### 4.3 `modules/rag-search-service` — Retrieval and Resource Administration

**Purpose:** Retrieves the most relevant indexed content for search and answer generation.

**What it does:**

- Provides vector, lexical, hybrid, graph, and combined search.
- Preprocesses queries and applies configurable aliases and filters.
- Oversamples candidates, normalizes scores, applies reciprocal-rank fusion, and reranks results.
- Checks result quality and creates concise, source-aware snippets.
- Excludes chunks marked non-searchable during ingestion.
- Exposes developer/debug search output when enabled.
- Lists resources with ingestion, chunk, embedding, and job statistics.
- Supports admin delete, retry, reindex, and Graph RAG runtime settings.

**Standalone UIs (port 8001):**

- `/ui/search`: interactive search form and ranked results.
- `/ui/admin/resources`: filterable resource table with metadata, counts, status, bulk deletion, retry, and indexing operations.

### 4.4 `modules/rag-answer-service` — Grounded Answer Generation

**Purpose:** Converts retrieved chunks into answers that remain grounded in library content.

**What it does:**

- Calls the RAG Search Service to obtain context.
- Builds source-ranked context and prompts with explicit citation instructions.
- Generates answers using OpenAI, Ollama, or Gemini providers.
- Verifies citations, named anchors, unsupported inference language, and basic faithfulness.
- Returns `insufficient_context` when retrieved evidence cannot support the question.
- Compares several models for the same question.
- Streams comparison progress/results with Server-Sent Events.

**Standalone UI (`/ui/answer`, port 8002):** Question input, search/context settings, answer and citation display, and model comparison controls.

### 4.5 `modules/online_library` — Structured Catalog API

**Purpose:** Exposes read-only structured library and account data from PostgreSQL.

**What it does:**

- Searches catalog resources by text, author, genre/category, tag, publisher, language, tier, status, and publication date.
- Returns book details, authors, tags, facets, pagination, and sorting.
- Provides business searches for authors, users, subscriptions, and approval requests.
- Provides paginated access to selected non-empty database tables for diagnostics.
- Omits large binary content from catalog responses.

This module is API-only and uses FastAPI's generated OpenAPI/Swagger page at `/docs` on port 8003.

### 4.6 `modules/online_library_mcp` — MCP Tool Server

**Purpose:** Makes Online Library API operations available as discoverable Model Context Protocol tools.

**What it does:**

- Runs a stateless MCP Streamable HTTP endpoint at `/mcp` on port 8004.
- Publishes typed tool names, descriptions, and input schemas through `tools/list`.
- Offers business tools for catalog, author, user, subscription, and approval searches.
- Retains lower-level table tools for admin diagnostics.
- Calls the Online Library REST API rather than accessing its database directly.

There is no custom end-user UI; developers can use MCP Inspector to connect, list tools, call them, and inspect responses.

### 4.7 `modules/online_library_agent` — Natural-Language Library Agent

**Purpose:** Answers natural-language questions about structured library data.

**What it does:**

- Discovers tools from the Online Library MCP server.
- Uses a local Ollama model to choose a tool and construct arguments.
- Applies deterministic routing rules for common requests such as books by author, genre, or tag.
- Calls the selected MCP tool and formats the result into a user-facing response.
- Returns diagnostics such as tool, arguments, model, fallback state, configuration, and timings.

**Standalone UI (`/ask`, port 8005):** Guided forms for common questions, an open-ended question box, formatted results, and developer diagnostics.

### 4.8 `modules/weather_agent` — Deterministic Weather POC

**Purpose:** Demonstrates a simple tool-backed agent without requiring an LLM.

It retrieves current conditions from weather.com with a `wttr.in` fallback and exposes a CLI, an HTML location form, and a JSON weather endpoint. The result includes temperature, conditions, feels-like temperature, humidity, wind, and source URL.

### 4.9 `modules/weather_ai_agent` — LLM Weather POC

**Purpose:** Demonstrates grounded LLM summarization of live weather observations.

It first uses the deterministic weather service, then asks a CrewAI agent backed by Gemini or Ollama to summarize only the retrieved facts. It includes CLI, HTML form, and JSON API interfaces.

## 5. Main User Workflows

### Search and answer

1. The user logs in through the secure UI.
2. Keycloak issues access and refresh tokens.
3. The UI submits a search or question to the gateway with the bearer token.
4. The gateway validates the token and roles.
5. Search retrieves and ranks chunks from PostgreSQL/pgvector.
6. For an answer request, the Answer Service sends selected context to the configured LLM.
7. Faithfulness/citation checks run before the response is returned to the UI.

### Ingest and index

1. An authorized administrator uploads a document and metadata.
2. The gateway forwards the multipart request to the Ingest Service.
3. The service extracts, cleans, chunks, and stores document content.
4. It creates vector embeddings, a graph index, both, or neither according to `indexing_mode`.
5. Job state and errors are persisted for monitoring and retry.
6. The resource becomes visible in Books, Catalog, Search, and Answer workflows when ready.

### Natural-language structured library query

1. The user asks a catalog/account question in Library Search.
2. The gateway forwards it to the Online Library Agent.
3. The agent discovers/selects an MCP tool and arguments.
4. MCP calls the matching Online Library API endpoint.
5. The agent formats the structured result for display.

## 6. Technology Stack

| Area | Technologies |
| --- | --- |
| Language/runtime | Python 3.13+ |
| Web/API framework | FastAPI, Uvicorn, Pydantic, pydantic-settings |
| HTTP clients | HTTPX |
| Database | PostgreSQL, SQLAlchemy, Psycopg 3 |
| Vector search | pgvector |
| Authentication | Keycloak, OAuth 2.0/OpenID Connect, JWT, PyJWT, JWKS |
| Agent framework | CrewAI |
| Tool protocol | Model Context Protocol (MCP), FastMCP, Streamable HTTP |
| LLM providers | Ollama/local models, OpenAI, Google Gemini |
| Embeddings | OpenAI embeddings or Ollama embeddings |
| Document processing | PyMuPDF, pypdf, python-docx, EPUB/OPF parsing |
| Async processing | FastAPI background tasks, database worker, RQ/Redis, or Kafka |
| Frontend | Server-served HTML, CSS, and vanilla JavaScript; Fetch API; browser `localStorage`; SSE |
| Testing/tools | pytest, Postman collections, MCP Inspector, PowerShell and batch scripts |
| Observability | Python logging, request IDs, W3C `traceparent`, trace/span headers, profiling records |
| Packaging | `pyproject.toml`, per-service requirements/lock files, editable local install |

## 7. Data and Storage

The RAG and online-library modules share a PostgreSQL database by default. The schema stores catalog resources and metadata alongside ingestion jobs, extracted text, chunks, embeddings, graph entities/relationships, processing errors, and profiling data. pgvector supplies vector similarity search.

Uploaded originals are stored temporarily on disk. Successful ingestion deletes the original by default while retaining the extracted/indexed data; failed jobs retain the file for troubleshooting. This behavior is configurable.

## 8. Security Model

- Keycloak is the identity provider; the gateway is the browser-facing policy enforcement point.
- Protected requests use bearer JWTs and role checks.
- Downstream services receive an internal API key plus forwarded user identity/role headers.
- Admin controls require admin roles at the gateway even if hidden in the UI.
- Detailed health output is designed not to expose secrets.
- The direct downstream UIs and admin endpoints are development conveniences and should not be publicly exposed without additional protection.

Current POC caveats include browser token storage in `localStorage`, no automatic UI token refresh, and local-development credentials/configuration that must be replaced before production use.

## 9. Default Local Service Map

| Port | Service | Main entry/UI |
| ---: | --- | --- |
| 8000 | RAG Ingest | `/ui` |
| 8001 | RAG Search | `/ui/search`, `/ui/admin/resources` |
| 8002 | RAG Answer | `/ui/answer` |
| 8003 | Online Library API | `/docs` |
| 8004 | Online Library MCP | `/mcp` |
| 8005 | Online Library Agent | `/ask` |
| 8010 | Secure API Gateway | `/ui` |
| 8080 | Keycloak | `/admin` and realm OIDC endpoints |
| 11434 | Ollama | Local model API |
| 5432 | PostgreSQL | Online Library/RAG database |

The two weather UIs also default to common development ports, so choose non-conflicting ports when running them alongside the RAG services.

## 10. Repository Layout

```text
My-Agent-Poc/
├── PROJECT_OVERVIEW.md
├── pyproject.toml
├── modules/
│   ├── secure_api/
│   ├── rag-ingest-service/
│   ├── rag-search-service/
│   ├── rag-answer-service/
│   ├── online_library/
│   ├── online_library_mcp/
│   ├── online_library_agent/
│   ├── weather_agent/
│   └── weather_ai_agent/
├── scripts/keycloak/
├── docs/
├── prompts/
├── TODO/
└── my_agent_poc-info/
```

Each service contains its own README and may also include an `.env.example`, tests, SQL, detailed design documents, a Postman collection, and a local run script.

## 11. Running and Validation Notes

- Apply the checked-in SQL schema before starting database-backed services.
- Start infrastructure first: PostgreSQL/pgvector, Keycloak, and Ollama or configured cloud providers.
- Start downstream services before the Secure API Gateway.
- Use the per-module README and `.env.example` for exact environment variables and commands.
- Run each module's pytest suite from that service directory.
- Use `/health` for liveness and `/ready` where provided for dependency readiness.
- Use the supplied Postman collections for API-level validation.
- Use MCP Inspector for direct MCP server validation.

## 12. Known Limitations and Recommended Next Steps

- `main.py` remains an unrelated PyCharm sample; a real top-level launcher would reduce confusion.
- Services are started separately; Docker Compose or Kubernetes manifests would simplify orchestration.
- Direct downstream development UIs do not share the gateway's full security boundary.
- The secure UI needs automatic refresh-token handling and stronger browser-session storage for production.
- Destructive admin actions need audit logging, soft delete/archive, and stronger confirmation safeguards.
- Centralized metrics, distributed tracing export, and dashboards would improve operations.
- CI should run formatting, linting, tests, dependency checks, and schema validation.
- Production deployment needs secret management, TLS, hardened CORS, rotated credentials, backups, and explicit network policies.
