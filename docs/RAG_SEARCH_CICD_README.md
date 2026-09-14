# rag-search-service CI/CD overlay

Copy this overlay into the root of the existing `My-Agent-Poc` repository.

## Added files

- `modules/rag-search-service/Dockerfile`
- `modules/rag-search-service/.dockerignore`
- `k8s/rag-search-service/configmap.yaml`
- `k8s/rag-search-service/deployment.yaml`
- `k8s/rag-search-service/service.yaml`
- `Jenkinsfile.rag-search`
- `scripts/test-rag-search-cicd.bat`

## Local validation

From repository root:

```powershell
.\scripts\test-rag-search-cicd.bat
```

The test stage is temporarily nonblocking. The source tests require a PostgreSQL database named `online_library_test`. If it does not exist, pytest will fail but the POC deployment continues.

## Jenkins

Create a separate Pipeline job from SCM and set Script Path to:

`Jenkinsfile.rag-search`

The service deploys into namespace `rag-poc` as `rag-search-service`, ClusterIP port `8001`.

## Dependencies

Runtime configuration expects:

- PostgreSQL/pgvector: `host.docker.internal:5432`, database `online_library`
- Ollama: `host.docker.internal:11434`, model `nomic-embed-text`
- RAG Ingest service DNS: `http://rag-ingest-service:8000`

`/health` does not require those dependencies to be healthy. `/ready` checks PostgreSQL and the configured embedding model.
