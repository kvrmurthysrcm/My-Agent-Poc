# Runbook

## Local startup order

1. PostgreSQL/pgvector, Keycloak, and Ollama or configured provider.
2. RAG Ingest `:8000`, Search `:8001`, Answer `:8002`.
3. Online Library `:8003`, MCP `:8004`, Library Agent `:8005`.
4. Secure API Gateway `:8010`.
5. Angular UI: `npm start` in `modules/angular-ui`.

## Quick validation

1. Open `http://localhost:4200/login` and authenticate.
2. Confirm Books loads via `/api/rag/resources`.
3. Test catalog, standard/graph/combined search, answer, and compare stream.
4. With allowed roles, upload a small TXT and verify polling reaches a terminal status.
5. With admin role, test a non-production resource operation and Graph RAG setting.
6. Test Library Search and raw library-tool discovery.

## Operational diagnostics

- Browser developer panel: returned trace/span/request IDs.
- Gateway logs: propagated trace context and safe downstream failure class.
- Gateway `/rag/test-downstream`: authenticated service availability overview.
- Service health/ready endpoints: dependency-specific health.

## Deployment

Run `npm run build`, serve `dist/rag-agent-angular-ui/browser` from a static host, configure SPA fallback to `index.html`, configure the gateway's allowed production origin, use HTTPS, and inject only browser-safe configuration. Do not deploy the development proxy or internal service URLs to production.
