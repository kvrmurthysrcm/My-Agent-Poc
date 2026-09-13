You are working inside my existing repository:

My-Agent-Poc/

Before changing anything, perform a thorough repository analysis.

GOAL
====

Create a NEW Angular frontend module that reproduces 100% of the functionality currently available through the existing browser-facing UI of this project.

This is both:

1. a working Angular POC for my existing RAG / Agent / Online Library system, and
2. a learning/reference project to help me prepare for a senior Java + Angular Architect interview.

Do NOT replace, rewrite, or break the existing Python/FastAPI backend services.

The Angular application should consume the existing Secure API Gateway and existing backend APIs.

The objective is functional parity with the existing browser UI, while demonstrating modern Angular architecture and current Angular best practices.

IMPORTANT:
Do not omit functionality merely because it is complicated.

If an existing UI capability cannot be implemented because an API or behavior is genuinely unavailable, document the exact reason and identify the missing backend capability.

Do not silently invent APIs.

==================================================
PHASE 0 — ANALYZE THE EXISTING APPLICATION FIRST
==================================================

Before generating Angular code:

1. Read the complete repository structure.
2. Read PROJECT_OVERVIEW.md.
3. Inspect:
   modules/secure_api
   modules/rag-ingest-service
   modules/rag-search-service
   modules/rag-answer-service
   modules/online_library
   modules/online_library_mcp
   modules/online_library_agent

4. Inspect all existing:
   - HTML
   - CSS
   - JavaScript
   - FastAPI routes
   - API schemas
   - Pydantic models
   - authentication logic
   - authorization logic
   - SSE endpoints
   - upload APIs
   - search APIs
   - admin APIs
   - catalog APIs
   - library-agent APIs

5. Build a COMPLETE UI FUNCTIONALITY INVENTORY.

6. Build an API inventory mapping:

   Existing UI function
       ->
   Current HTTP endpoint
       ->
   Method
       ->
   Request model
       ->
   Response model
       ->
   Required role
       ->
   Angular screen/component/service

7. Save this analysis BEFORE implementation as:

   modules/angular-ui/docs/EXISTING_UI_FUNCTIONALITY_INVENTORY.md

   and:

   modules/angular-ui/docs/API_ENDPOINT_MAPPING.md

8. Do not begin major implementation until this inventory is complete.

==================================================
NEW MODULE
==================================================

Create:

modules/angular-ui/

Use the latest STABLE Angular 22.x release available from npm.

Use the matching Angular CLI version.

Do NOT use beta, next, RC, or experimental releases unless a feature is already stable.

Use TypeScript strict mode.

Application name:

rag-agent-angular-ui

Suggested local development port:

4200

The backend Secure API Gateway remains:

http://localhost:8010

Do not call PostgreSQL, Keycloak admin APIs, RAG databases, or internal downstream services directly unless the existing frontend already does so intentionally.

The normal Angular frontend architecture must be:

Browser
   |
   v
Angular :4200
   |
   v
Secure API Gateway :8010
   |
   +--> Keycloak :8080
   +--> RAG Ingest :8000
   +--> RAG Search :8001
   +--> RAG Answer :8002
   +--> Online Library :8003
   +--> MCP :8004
   +--> Library Agent :8005

==================================================
ANGULAR ARCHITECTURE
==================================================

Use modern Angular architecture.

Prefer standalone Angular APIs rather than creating unnecessary NgModules.

Demonstrate current Angular capabilities including:

- standalone components
- signals
- computed signals
- effects where appropriate
- dependency injection with inject()
- strongly typed services
- reactive forms
- typed forms
- HttpClient
- functional HTTP interceptors
- functional route guards
- lazy-loaded routes
- route-level authorization
- centralized error handling
- loading/error/empty states
- RxJS where streams are genuinely appropriate
- signals for application/UI state where appropriate
- ChangeDetectionStrategy.OnPush where applicable
- control flow syntax:
    @if
    @for
    @switch
- reusable components
- container/presentation separation where useful
- accessibility
- responsive layouts
- strongly typed API DTOs
- environment configuration
- production build configuration

Do NOT add NgRx merely to demonstrate NgRx.

Use Angular's built-in capabilities first.

If application state becomes sufficiently complex to justify a store, implement a lightweight signal-based store/facade pattern and explain the decision.

==================================================
PROPOSED SOURCE STRUCTURE
==================================================

Use a structure similar to:

modules/angular-ui/
│
├── README.md
├── package.json
├── angular.json
├── tsconfig.json
├── proxy.conf.json
│
├── prompts/
│   ├── 00-master-angular-poc-prompt.md
│   ├── 01-repository-analysis-prompt.md
│   ├── 02-authentication-prompt.md
│   ├── 03-books-catalog-prompt.md
│   ├── 04-search-prompt.md
│   ├── 05-answer-prompt.md
│   ├── 06-model-compare-sse-prompt.md
│   ├── 07-ingestion-admin-prompt.md
│   ├── 08-library-agent-prompt.md
│   ├── 09-testing-prompt.md
│   └── 10-angular-interview-review-prompt.md
│
├── docs/
│   ├── ARCHITECTURE.md
│   ├── EXISTING_UI_FUNCTIONALITY_INVENTORY.md
│   ├── FUNCTIONAL_PARITY_MATRIX.md
│   ├── API_ENDPOINT_MAPPING.md
│   ├── AUTHENTICATION_AND_AUTHORIZATION.md
│   ├── ANGULAR_CONCEPTS_USED.md
│   ├── STATE_MANAGEMENT.md
│   ├── HTTP_AND_INTERCEPTORS.md
│   ├── ROUTING_AND_GUARDS.md
│   ├── SSE_STREAMING.md
│   ├── ERROR_HANDLING.md
│   ├── TESTING_STRATEGY.md
│   ├── SECURITY_NOTES.md
│   ├── INTERVIEW_GUIDE.md
│   └── RUNBOOK.md
│
└── src/
    └── app/
        ├── core/
        │   ├── auth/
        │   ├── guards/
        │   ├── interceptors/
        │   ├── http/
        │   ├── models/
        │   ├── services/
        │   └── config/
        │
        ├── shared/
        │   ├── components/
        │   ├── directives/
        │   ├── pipes/
        │   ├── models/
        │   └── utils/
        │
        ├── layout/
        │   ├── shell/
        │   ├── header/
        │   ├── navigation/
        │   └── theme/
        │
        └── features/
            ├── auth/
            ├── books/
            ├── catalog/
            ├── search/
            ├── answer/
            ├── compare/
            ├── ingest/
            ├── admin/
            ├── library-search/
            └── library-tools/

Adjust the structure if repository analysis indicates a better decomposition.

Document every important architectural decision.

==================================================
FUNCTIONAL PARITY — MANDATORY
==================================================

The Angular UI must reproduce ALL functionality of the existing Secure API UI.

At minimum this includes:

AUTHENTICATION
--------------

- Login
- Registration
- Logout
- Access-token handling
- Refresh-token handling
- Current-user lookup
- Role extraction/display
- Authentication state
- Unauthorized handling
- Expired-session behavior

The existing POC stores tokens in localStorage.

For functional parity, understand the existing implementation first.

Then:

1. reproduce required behavior,
2. isolate token/session management behind an AuthService,
3. document the security implications,
4. document the recommended production alternative.

Do not weaken backend authorization.

ROLE-BASED AUTHORIZATION
------------------------

Support the existing roles including:

- ordinary users
- search users
- ingest users
- rag_admin
- system_admin

Implement:

- route guards
- UI visibility checks
- centralized role helpers

But clearly document:

UI authorization != security boundary.

Backend authorization remains authoritative.

==================================================
APPLICATION SHELL
==================================================

Create a professional responsive application shell with:

- header
- navigation
- logged-in user
- role information
- theme toggle
- dark/light theme
- persisted theme preference
- logout

Provide navigation based on authorized capabilities.

==================================================
BOOKS DASHBOARD
==================================================

Reproduce the current Books functionality including:

- resource list
- resource metadata
- ingestion status
- chunk count
- embedding/index state
- Graph RAG state
- refresh
- selection
- resource detail
- status badges
- admin operations where authorized

==================================================
CATALOG
==================================================

Support structured online-library catalog functionality including:

- text search
- author filter
- genre/category
- tags
- publisher
- language
- tier
- status
- publication-date filters
- pagination
- sorting
- facets where available
- book/resource details
- authors
- tags

==================================================
CONTENT SEARCH
==================================================

Reproduce all search functionality exposed by the existing UI/API.

Support:

- lexical search
- vector search
- hybrid search
- graph search
- combined search
- query preprocessing
- metadata filters
- result limits/settings
- ranked results
- score display
- source-aware snippets
- developer/debug output where available

Create reusable result components.

==================================================
GROUNDED ANSWER
==================================================

Support:

- question input
- search/context configuration
- answer generation
- citations
- source display
- insufficient_context handling
- faithfulness/validation information if returned
- provider/model information when available
- error/loading state

==================================================
MODEL COMPARISON
==================================================

Reproduce multi-model answer comparison.

This includes Server-Sent Events.

Implement a dedicated Angular streaming abstraction.

Support:

- selecting models
- submitting one question
- progress events
- partial/completed results
- per-model status
- per-model failures
- final side-by-side comparison
- cancellation if the existing API permits it
- clean teardown when the component is destroyed

Document how SSE works in:

docs/SSE_STREAMING.md

Explain:

HTTP request
    ->
server keeps connection open
    ->
events arrive incrementally
    ->
Angular updates model state
    ->
UI renders progress/results

==================================================
DOCUMENT INGESTION
==================================================

Admin/authorized ingest functionality must support:

- file upload
- TXT
- PDF
- DOCX
- EPUB
- multipart/form-data
- metadata input
- metadata preview if currently available
- chunking mode
- indexing mode:
    NONE
    STANDARD
    GRAPH
    BOTH
- embedding/provider controls exposed by current APIs
- job status
- polling
- success/failure
- validation messages
- progress/status display

==================================================
RESOURCE ADMINISTRATION
==================================================

Reproduce:

- resource filtering
- ingestion state
- chunk counts
- embeddings
- job statistics
- deletion
- bulk deletion if existing UI supports it
- retry failed jobs
- standard embedding/index creation
- Graph RAG indexing
- reindex operations
- runtime Graph RAG controls exposed by existing APIs

Destructive actions must have confirmation UX.

==================================================
LIBRARY SEARCH / AGENT
==================================================

Support the natural-language Library Search flow:

User
   ->
Angular
   ->
Secure API Gateway
   ->
Online Library Agent
   ->
MCP
   ->
Online Library API

Include:

- guided/common queries if current UI provides them
- free-text question
- formatted result
- selected tool
- tool arguments
- model
- fallback state
- timing/configuration diagnostics when returned
- developer diagnostics collapsible panel

==================================================
RAW LIBRARY TOOLS
==================================================

Where the existing admin UI exposes raw MCP/library tools:

- preserve that functionality
- role-protect it
- create typed forms for tool arguments
- render structured JSON results cleanly
- allow developer-friendly JSON inspection

==================================================
TRACEABILITY / OBSERVABILITY
==================================================

Preserve or expose the existing request tracing model where possible.

Support:

- X-Trace-Id
- X-Span-Id
- request IDs
- traceparent

Do not fabricate server trace IDs.

Where returned by the server, make them visible in a developer/debug panel.

Implement an HTTP interceptor that can create/propagate appropriate client request correlation data if consistent with the existing gateway contract.

Document the implementation.

==================================================
ERROR HANDLING
==================================================

Implement centralized HTTP error handling.

Distinguish at least:

- 400 validation
- 401 unauthenticated
- 403 unauthorized
- 404
- 409/conflict
- 422 validation
- 500/server errors
- network unavailable
- gateway unavailable
- timeout

Present user-friendly messages while retaining developer diagnostics.

==================================================
ANGULAR FEATURES TO TEACH
==================================================

This POC is specifically for Angular learning/interview preparation.

Therefore every significant Angular concept should be EASY TO FIND.

For important files, use concise comments such as:

// ANGULAR CONCEPT: signal
// ANGULAR CONCEPT: computed signal
// ANGULAR CONCEPT: dependency injection
// ANGULAR CONCEPT: functional interceptor
// ANGULAR CONCEPT: route guard
// ANGULAR CONCEPT: reactive form
// ANGULAR CONCEPT: lazy loading

Do not over-comment trivial TypeScript.

Create:

docs/ANGULAR_CONCEPTS_USED.md

For every concept include:

1. What it is
2. Why Angular provides it
3. Where this project uses it
4. A small code example
5. Common interview question
6. Concise interview answer

Cover at minimum:

- Angular architecture
- components
- standalone components
- templates
- data binding
- property binding
- event binding
- two-way binding and when NOT to use it
- signals
- computed
- effect
- RxJS
- Observable
- Subject / BehaviorSubject where relevant
- signals vs Observables
- dependency injection
- providers
- inject()
- services
- HttpClient
- interceptors
- routing
- lazy loading
- guards
- reactive forms
- form validation
- pipes
- directives
- lifecycle
- OnPush
- change detection
- control flow
- error handling
- environment/configuration
- authentication
- authorization
- CORS
- unit testing
- component testing
- HTTP testing
- accessibility
- performance optimization

==================================================
STATE MANAGEMENT
==================================================

Do not introduce unnecessary complexity.

Prefer:

Component local state
    ->
signals

Shared feature state
    ->
feature service/facade + signals

Async HTTP streams
    ->
RxJS

Explain the boundary between Signals and RxJS.

Create:

docs/STATE_MANAGEMENT.md

Include a diagram such as:

Component
   |
   v
Feature Facade / Store
   |
   +--> signals
   |
   +--> API service
            |
            v
         HttpClient
            |
            v
       Secure Gateway

==================================================
HTTP ARCHITECTURE
==================================================

Use dedicated API services.

Do NOT scatter HttpClient calls throughout components.

Example organization:

AuthApiService
ResourceApiService
CatalogApiService
SearchApiService
AnswerApiService
IngestApiService
LibraryAgentApiService
AdminApiService

Use DTOs/interfaces rather than `any`.

No `any` unless unavoidable and explicitly justified.

==================================================
AUTH INTERCEPTOR
==================================================

Create a functional HTTP interceptor that:

- attaches bearer token where appropriate
- preserves multipart uploads
- handles 401 behavior
- coordinates refresh-token flow if compatible with the existing gateway
- avoids concurrent refresh storms
- does not attach credentials to unrelated external URLs

Document the flow.

==================================================
ROUTING
==================================================

Use lazy feature routes.

Suggested routes:

/login
/register
/books
/catalog
/search
/answer
/compare
/library-search
/ingest
/admin/resources
/admin/library-tools

Use:

authGuard
roleGuard

Use a shell route for authenticated screens.

==================================================
TESTING
==================================================

Implement meaningful automated tests.

Use the current recommended Angular test tooling generated/supported by Angular 22 unless repository constraints require otherwise.

At minimum test:

- AuthService
- auth interceptor
- guards
- role authorization
- SearchApiService
- AnswerApiService
- ingestion form validation
- model comparison streaming
- major page components
- error handling

Do not create meaningless coverage-only tests.

Create:

docs/TESTING_STRATEGY.md

==================================================
UI / UX
==================================================

The UI should be professional but should NOT require a huge third-party UI framework.

Prefer modern semantic HTML + CSS.

If you choose Angular Material, explain why before adding it.

Requirements:

- responsive
- keyboard accessible
- clear labels
- loading indicators
- disabled states
- empty states
- errors
- success messages
- confirmation dialogs
- accessible forms
- readable tables/cards
- dark/light theme

Preserve functionality over decorative design.

==================================================
SECURITY
==================================================

Create:

docs/SECURITY_NOTES.md

Explain:

- Keycloak/OIDC architecture
- JWT
- access vs refresh token
- token expiry
- role-based UI behavior
- backend authorization
- localStorage risk
- XSS implications
- recommended production token/session design
- CORS
- CSRF considerations
- API-key boundary
- why the browser must NOT receive the downstream internal X-API-Key

IMPORTANT:
The Angular browser must never expose the internal backend API key.

The Secure API Gateway remains responsible for adding internal service credentials.

==================================================
DOCUMENTATION
==================================================

Create comprehensive docs.

ARCHITECTURE.md
---------------

Include diagrams for:

Browser
   |
Angular
   |
Secure API Gateway
   |
backend services

Also document:

component architecture
routing
API layer
authentication
authorization
state management
SSE
error handling

FUNCTIONAL_PARITY_MATRIX.md
---------------------------

This is mandatory.

Use a table:

Existing capability
Existing UI/location
Backend endpoint
Angular route
Angular implementation
Test
Status

Every original capability must eventually show:

COMPLETE

Do not claim completion without implementing and testing it.

==================================================
INTERVIEW GUIDE
==================================================

Create:

docs/INTERVIEW_GUIDE.md

This should help me prepare for a Java + Angular Architect interview.

For each important project capability explain:

- Angular concept involved
- Why it was designed this way
- alternative approaches
- trade-offs
- architect-level discussion point

Include at least 50 Angular interview questions with concise answers.

Group them:

1. Angular fundamentals
2. components/templates
3. signals
4. RxJS
5. dependency injection
6. HTTP
7. routing/guards
8. forms
9. state management
10. performance/change detection
11. security
12. testing
13. architecture
14. Java/Spring + Angular integration

Also include scenario questions such as:

"How would you structure a large Angular enterprise application?"

"Signals vs RxJS — when would you use each?"

"How does an Angular SPA integrate with a Spring Boot backend?"

"Where should authentication tokens be stored?"

"How would you implement authorization?"

"How would you handle token refresh?"

"How do interceptors work?"

"How would you stream server events?"

"How do you prevent memory leaks?"

"How do you improve Angular performance?"

"How would you split a monolithic Angular application?"

==================================================
PROMPTS FOLDER
==================================================

Create:

modules/angular-ui/prompts/

Save THIS ENTIRE MASTER PROMPT as:

00-master-angular-poc-prompt.md

Then create smaller reusable Codex prompts for:

repository analysis
authentication
routing
API integration
search
answer generation
SSE
ingestion
admin
testing
code review
Angular interview preparation

The purpose is to allow me to later ask Codex to regenerate, inspect, improve, or explain individual areas.

==================================================
LEARNING MODE
==================================================

This repository should be understandable by reading the code.

For each feature README/doc, include:

WHAT
WHY
HOW
ANGULAR CONCEPT
INTERVIEW TAKEAWAY

Example:

WHAT:
Auth interceptor adds JWT to API requests.

WHY:
Avoid repeating token attachment logic across services.

HOW:
Angular functional interceptor uses inject(AuthService).

ANGULAR CONCEPT:
HTTP Interceptor + Dependency Injection.

INTERVIEW TAKEAWAY:
Interceptors implement cross-cutting HTTP concerns such as authentication,
logging, correlation IDs, retries, and centralized error handling.

==================================================
DEVELOPMENT PROXY
==================================================

Configure local Angular development so API calls can be made cleanly without hard-coded repeated URLs.

Consider:

proxy.conf.json

Angular:
http://localhost:4200

Gateway:
http://localhost:8010

Document how proxying affects CORS during development.

Do not hide actual production CORS requirements.

==================================================
README
==================================================

Create a comprehensive:

modules/angular-ui/README.md

Include:

- purpose
- prerequisites
- required Node version
- Angular version
- installation
- npm commands
- development startup
- proxy configuration
- backend startup dependencies
- login flow
- test users/roles only if already documented safely
- test execution
- production build
- troubleshooting
- project structure

==================================================
VALIDATION
==================================================

After implementation:

1. npm install
2. compile application
3. run lint if configured
4. run tests
5. run production build
6. inspect TypeScript errors
7. inspect console warnings
8. validate routes
9. validate all APIs against current backend contracts

Do not stop after generating files.

Fix issues until the Angular project builds successfully.

==================================================
FUNCTIONAL PARITY VALIDATION
==================================================

Before declaring the project finished:

Re-open the original Secure API UI.

Compare every screen, control, action, workflow, filter, option, and admin capability.

Update:

docs/FUNCTIONAL_PARITY_MATRIX.md

Nothing should remain:

UNKNOWN
TODO
NOT CHECKED

unless it genuinely requires a running external dependency that cannot be started.

If something cannot be validated, clearly document:

- capability
- reason
- expected behavior
- exact validation procedure

==================================================
DO NOT
==================================================

Do NOT:

- modify backend APIs merely to simplify Angular
- duplicate backend security logic in the browser
- expose internal API keys
- invent missing endpoints
- remove existing functionality
- simplify Graph RAG functionality away
- omit admin operations
- omit SSE comparison
- omit MCP/library-agent functionality
- replace strongly typed DTOs with any
- add large dependencies without justification
- put all logic in one giant component
- create a tutorial toy application
- stop after scaffolding

This must be a realistic enterprise Angular POC.

==================================================
DELIVERY PROCESS
==================================================

Work incrementally.

STEP 1:
Analyze repository and produce inventory/docs.

STEP 2:
Show me:
- functionality inventory
- proposed Angular architecture
- API mapping
- any ambiguities/questions

STEP 3:
Only ask me questions if information genuinely cannot be determined from the repository.

STEP 4:
Scaffold Angular project.

STEP 5:
Implement authentication + shell.

STEP 6:
Implement Books/Catalog.

STEP 7:
Implement Search/Answer/Compare.

STEP 8:
Implement Ingestion/Admin.

STEP 9:
Implement Library Agent/tools.

STEP 10:
Tests, documentation, build validation.

STEP 11:
Perform final parity review.

At each major phase, update documentation.

==================================================
FINAL REPORT
==================================================

At completion produce:

modules/angular-ui/docs/IMPLEMENTATION_REPORT.md

Include:

- Angular version
- Node version
- architecture summary
- implemented features
- test results
- build results
- functional parity status
- known limitations
- security observations
- backend changes (ideally none)
- key Angular concepts demonstrated
- recommended next learning exercises

Also provide a concise console summary:

Angular POC: COMPLETE / PARTIAL
Build: PASS / FAIL
Tests: PASS / FAIL
Functional parity: <percentage>
Remaining issues: <count>

Do not call the work 100% complete unless the parity matrix genuinely demonstrates it.


the Target architecture would be like this:

                Browser
                   │
                   ▼
        ┌─────────────────────┐
        │ Angular 22 SPA      │
        │ localhost:4200      │
        │                     │
        │ Components          │
        │ Signals / RxJS      │
        │ Reactive Forms      │
        │ Guards              │
        │ Interceptors        │
        │ Typed API Services  │
        └──────────┬──────────┘
                   │
                   │ REST / SSE
                   ▼
        ┌─────────────────────┐
        │ Secure API Gateway  │
        │ :8010               │
        └──────────┬──────────┘
                   │
       ┌───────────┼─────────────┐
       │           │             │
       ▼           ▼             ▼
    Ingest       Search        Answer
     :8000        :8001         :8002
                                 │
       ┌───────────┬─────────────┘
       ▼           ▼
   Library       MCP / Agent
    :8003       :8004 / :8005

                   +
                Keycloak
                  :8080
