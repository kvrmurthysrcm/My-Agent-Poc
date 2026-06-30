# Secure API Gateway

Base scaffold for the FastAPI wrapper service that will later validate Keycloak JWTs and call downstream RAG services.

Phase 2 scope only:

- FastAPI application startup
- `.env` based configuration
- Request logging middleware
- Consistent JSON error responses
- CORS for local frontend ports
- Health endpoints
- Local run scripts
- Health tests

Keycloak authentication and RAG downstream proxy routes are intentionally not implemented in this phase.

## Requirements

- Python 3.11+
- Keycloak setup from phase 1, for later phases

Install dependencies:

```powershell
pip install -r .\modules\secure_api\requirements.txt
```

Create a local environment file if needed:

```powershell
Copy-Item .\modules\secure_api\.env.example .\modules\secure_api\.env
```

## Run Locally

PowerShell:

```powershell
.\modules\secure_api\run_local.ps1
```

Batch file:

```bat
.\modules\secure_api\run_local.bat
```

The app runs at:

```text
http://localhost:8010
```

The batch file prints the service PID and a `taskkill` command that can be used to stop it later.

## Health Endpoints

Basic health:

```text
GET http://localhost:8010/health
```

Expected response:

```json
{"status":"UP"}
```

Detailed health:

```text
GET http://localhost:8010/health/details
```

The detailed endpoint returns service metadata but does not expose secrets.

## Tests

```powershell
cd .\modules\secure_api
pytest
```

## Future Phases

- Phase 3: Keycloak login, refresh, and logout routes
- Phase 4: JWT validation and `/auth/me`
- Phase 5: Protected RAG gateway routes using downstream API key auth
- Phase 6: Quality pass and hardening
