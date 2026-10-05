# Step 2 — Add Kubernetes OTel Configuration Script

Context:
- Python FastAPI services run as Kubernetes pods in Docker Desktop on Windows.
- Grafana LGTM runs as a separate Docker container.
- Grafana: http://localhost:3000
- OTLP HTTP: http://host.docker.internal:4318
- Services: rag-answer-service, rag-search-service, rag-ingest-service.

Modify only `scripts/configure-otel-k8s.bat`. Do not change Python, Dockerfiles, requirements, or K8s YAML.

Requirements:
- Usage: `configure-otel-k8s.bat <deployment> <otel-service-name> [namespace]`
- Default namespace: `default`
- Endpoint: `http://host.docker.internal:4318`
- Set:
  - OTEL_SERVICE_NAME
  - OTEL_RESOURCE_ATTRIBUTES=service.namespace=rag-poc,deployment.environment=local
  - OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318
  - OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
  - OTEL_TRACES_EXPORTER=otlp
  - OTEL_METRICS_EXPORTER=otlp
  - OTEL_LOGS_EXPORTER=otlp
  - OTEL_PYTHON_LOG_CORRELATION=true
- Verify kubectl and Deployment exist.
- Use `kubectl set env`.
- Wait with `kubectl rollout status`.
- Print OTEL_* values.
- Do not assume the `app` label equals Deployment name.
- Fail clearly on errors.

Show the final script and diff. Do not run it yet.
