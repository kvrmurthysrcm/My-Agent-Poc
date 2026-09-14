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
- Root/shared/pipeline/unknown changes (for example `Jenkinsfile`, `pyproject.toml`, or `k8s/namespace.yaml`): all five deployable services are rebuilt as the conservative safe default.
- Source changes in modules not yet deployed by this pipeline (Angular UI, library agent/MCP, weather agents): no current Kubernetes service is redeployed.

## Important limitation

Because the decision is intentionally kept in the Jenkinsfile, a docs-only Git push can still trigger a short Jenkins run. Jenkins must checkout/read the Jenkinsfile before the pipeline can determine that only `docs/**` changed. That run performs no Docker build and no Kubernetes deployment.

## Change comparison

The pipeline prefers Jenkins SCM metadata (`GIT_PREVIOUS_SUCCESSFUL_COMMIT` / `GIT_PREVIOUS_COMMIT`) and falls back to `HEAD^`. This handles multiple commits between Jenkins polls better than always comparing only the last two Git commits.
