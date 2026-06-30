# Secure API Gateway

Base scaffold for the FastAPI wrapper service that will later validate Keycloak JWTs and call downstream RAG services.

Implemented scope:

- FastAPI application startup
- `.env` based configuration
- Request logging middleware
- Consistent JSON error responses
- CORS for local frontend ports
- Health endpoints
- Keycloak-backed login, refresh, and logout endpoints
- Local run scripts
- Health and auth tests

JWT validation, `/auth/me`, and RAG downstream proxy routes are intentionally not implemented yet.

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

## Auth Endpoints

Login:

```text
POST http://localhost:8010/auth/login
```

```json
{"username":"raguser","password":"raguser123"}
```

Refresh:

```text
POST http://localhost:8010/auth/refresh
```

```json
{"refresh_token":"<refresh-token>"}
```

Logout:

```text
POST http://localhost:8010/auth/logout
```

```json
{"refresh_token":"<refresh-token>"}
```

The service calls Keycloak at `http://localhost:8080` using realm `poc-realm` and client `fastapi-auth-gateway` by default. Override these values in `.env` if needed.

## Tests

```powershell
cd .\modules\secure_api
pytest
```

## Future Phases

- Phase 4: JWT validation and `/auth/me`
- Phase 5: Protected RAG gateway routes using downstream API key auth
- Phase 6: Quality pass and hardening
