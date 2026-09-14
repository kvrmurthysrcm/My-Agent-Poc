# Cumulative CI/CD - Secure API + Online Library + Ingest + Search + Answer

This overlay adds `online_library` to the already working cumulative stack.

| Service | Kubernetes service | Port |
|---|---|---:|
| RAG Ingest | `rag-ingest-service` | 8000 |
| RAG Search | `rag-search-service` | 8001 |
| RAG Answer | `rag-answer-service` | 8002 |
| Online Library | `online-library` | 8003 |
| Secure API | `secure-api` | 8010 |

`online_library` runs as `modules.online_library.api:app`, is read-only, does not require Ollama, and connects to PostgreSQL at `host.docker.internal:5432/online_library`.

Run the complete validation from the repository root:

```powershell
.\scripts\test-all-cicd.bat
```

Start local forwards:

```powershell
.\scripts\start-port-forwards.bat
```

Useful Online Library URLs after forwarding:

- `http://localhost:8003/health/db`
- `http://localhost:8003/docs`
- `http://localhost:8003/catalog/resources`
- `http://localhost:8003/catalog/facets`

The Online Library readiness probe uses `/health/db`; liveness is a TCP probe on 8003. Existing local POC DB credentials are retained for now and should later move to Kubernetes/Jenkins secret management.
