# Step 1 — Inspect OpenTelemetry Readiness

Context:
- Python FastAPI services run as Kubernetes pods in Docker Desktop on Windows.
- Grafana LGTM runs as a separate Docker container.
- Grafana: http://localhost:3000
- OTLP HTTP: http://host.docker.internal:4318
- Services: rag-answer-service, rag-search-service, rag-ingest-service.

Do not modify files, rebuild images, or deploy anything.

Inspect:
1. Python service directories and dependency files.
2. Dockerfiles and current Uvicorn/FastAPI startup commands.
3. Kubernetes Deployments/Helm/Kustomize/scripts.
4. Existing OTEL_* variables and tracing/correlation IDs.
5. Use of FastAPI, Uvicorn, httpx, requests, SQLAlchemy, Redis, PostgreSQL.
6. Existing configure-otel scripts.
7. Docker image names/tags and build/deploy process.

Return:
- current state
- files that need modification
- exact recommended changes
- risks/inconsistencies
- proposed execution order

Do not make changes until the next step is approved.
