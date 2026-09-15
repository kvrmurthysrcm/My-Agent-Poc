# Selective CI/CD in the single Jenkins pipeline

The root `Jenkinsfile` remains the only deployment pipeline.

## Behavior

- Changes only under `docs/`: Jenkins performs checkout + change detection, then skips Docker/Kubernetes stages.
- `modules/rag-ingest-service/**` or `k8s/rag-ingest-service/**`: Ingest only.
- `modules/rag-search-service/**` or `k8s/rag-search-service/**`: Search only.
- `modules/rag-answer-service/**` or `k8s/rag-answer-service/**`: Answer only.
- `modules/online_library/**` or `k8s/online-library/**`: Online Library only.
- `modules/secure_api/**` or `k8s/secure-api/**`: Secure API only.
- Changes in more than one mapped service: only those services are processed.
- `modules/online_library_mcp/**` or `k8s/online-library-mcp/**`: Online Library MCP only.
- `modules/online_library_agent/**` or `k8s/online-library-agent/**`: Online Library Agent only.
- `modules/weather_agent/**` or `k8s/weather-agent/**`: Weather Agent and its dependent Weather AI Agent.
- `modules/weather_ai_agent/**` or `k8s/weather-ai-agent/**`: Weather AI Agent only.
- `modules/angular-ui/**` or `k8s/angular-ui/**`: Angular UI only.
- Root/shared/pipeline/unknown changes (for example `Jenkinsfile`, `pyproject.toml`, or `k8s/namespace.yaml`): all ten deployable services are rebuilt as the conservative safe default.

## Important limitation

Because the decision is intentionally kept in the Jenkinsfile, a docs-only Git push can still trigger a short Jenkins run. Jenkins must checkout/read the Jenkinsfile before the pipeline can determine that only `docs/**` changed. That run performs no Docker build and no Kubernetes deployment.

## Change comparison

The pipeline prefers Jenkins SCM metadata (`GIT_PREVIOUS_SUCCESSFUL_COMMIT` / `GIT_PREVIOUS_COMMIT`) and falls back to `HEAD^`. This handles multiple commits between Jenkins polls better than always comparing only the last two Git commits.
