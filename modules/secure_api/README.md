# FastAPI Keycloak Auth Gateway

This module is a local POC wrapper service for authenticating users through Keycloak before calling protected APIs.

Current service URL:

```text
http://localhost:8010
```

Current Keycloak URL:

```text
http://localhost:8080
```

## Phase Status

| Phase | Scope | Status | Validation |
| --- | --- | --- | --- |
| Phase 1 | Keycloak realm, client, roles, users, token verification scripts | Done | `.\scripts\keycloak\02-keycloak-verify.ps1` |
| Phase 2 | FastAPI scaffold, config, logging, CORS, health endpoints | Done | `GET /health`, unit tests |
| Phase 3 | Keycloak-backed `/auth/login`, `/auth/refresh`, `/auth/logout` | Done | Wrapper auth curl commands below |
| Phase 4 | JWT validation, role extraction, protected `/auth/me` | Done | `GET /auth/me` with bearer token |
| Phase 5 | Protected RAG gateway routes using downstream `X-API-Key` | Not implemented yet | `/rag/*` routes currently return `404` |
| Phase 6 | Final hardening, full README, security review | In progress | This README covers current validation |

## Implemented Components

- Keycloak setup scripts under `scripts/keycloak`
- FastAPI app startup in `app/main.py`
- Environment-driven config in `app/config.py`
- Request logging middleware with `X-Request-ID`
- Consistent JSON error responses
- CORS for local frontend origins
- `GET /health`
- `GET /health/details`
- `POST /auth/login`
- `POST /auth/refresh`
- `POST /auth/logout`
- JWT validation with cached Keycloak JWKS
- Realm and client role extraction
- Protected `GET /auth/me`
- Unit tests for health, auth, JWT validation, role extraction, and `/auth/me`

## Local Configuration

The checked-in Keycloak scripts create and verify this realm:

```text
rag-auth-gateway
```

Create a local `.env` file:

```powershell
Copy-Item .\modules\secure_api\.env.example .\modules\secure_api\.env
```

Expected important values:

```env
KEYCLOAK_URL=http://localhost:8080
KEYCLOAK_REALM=rag-auth-gateway
KEYCLOAK_CLIENT_ID=fastapi-auth-gateway
KEYCLOAK_CLIENT_SECRET=fastapi-auth-gateway-secret
TOKEN_AUDIENCE_VALIDATION_ENABLED=false
```

## Start Services

Start Keycloak first. The expected container name is:

```text
local-keycloak
```

Confirm it is running:

```powershell
docker ps --filter "name=local-keycloak"
```

Start the wrapper service:

```powershell
.\modules\secure_api\run_local.ps1
```

Or:

```bat
.\modules\secure_api\run_local.bat
```

## Validate Phase 1: Keycloak Directly

Run the automated verification script from the repository root:

```powershell
.\scripts\keycloak\02-keycloak-verify.ps1
```

Expected result:

```text
Checking discovery document...
  OK: http://localhost:8080/realms/rag-auth-gateway/.well-known/openid-configuration
Checking JWKS document...
  OK: http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/certs

Requesting user tokens...
  OK: raguser received access_token with expected realm roles: eyJhbGciOiJSUzI1NiIsInR5cCIgOi...
  OK: ragadmin received access_token with expected realm roles: eyJhbGciOiJSUzI1NiIsInR5cCIgOi...
  OK: searchuser received access_token with expected realm roles: eyJhbGciOiJSUzI1NiIsInR5cCIgOi...
```

Check the discovery URL manually:

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8080/realms/rag-auth-gateway/.well-known/openid-configuration"
```

Equivalent curl:

```bash
curl -s http://localhost:8080/realms/rag-auth-gateway/.well-known/openid-configuration
```

Expected response includes:

```json
{
  "issuer": "http://localhost:8080/realms/rag-auth-gateway",
  "token_endpoint": "http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/token",
  "jwks_uri": "http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/certs"
}
```

Check JWKS manually:

```powershell
Invoke-RestMethod -Method Get `
  -Uri "http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/certs"
```

Equivalent curl:

```bash
curl -s http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/certs
```

Expected response includes a non-empty `keys` array.

Generate a token directly from Keycloak:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/token" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body @{
    grant_type = "password"
    client_id = "fastapi-auth-gateway"
    client_secret = "fastapi-auth-gateway-secret"
    username = "raguser"
    password = "raguser123"
    scope = "openid profile email"
  }
```

Equivalent curl:

```bash
curl -s -X POST "http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/token" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=password" \
  -d "client_id=fastapi-auth-gateway" \
  -d "client_secret=fastapi-auth-gateway-secret" \
  -d "username=raguser" \
  -d "password=raguser123" \
  -d "scope=openid profile email"
```

Expected response shape:

```json
{
  "access_token": "<jwt>",
  "expires_in": 300,
  "refresh_expires_in": 1800,
  "refresh_token": "<jwt-or-token>",
  "token_type": "Bearer",
  "scope": "profile email"
}
```

Other test users:

| Username | Password | Expected roles |
| --- | --- | --- |
| `raguser` | `raguser123` | `rag_user`, `rag_search_user` |
| `ragadmin` | `ragadmin123` | `rag_admin`, `rag_user`, `rag_search_user`, `rag_ingest_user`, `graph_rag_user`, `system_admin` |
| `searchuser` | `searchuser123` | `rag_search_user` |

## Validate Phase 2: Wrapper Health

Health:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8010/health"
```

Equivalent curl:

```bash
curl -s http://localhost:8010/health
```

Expected response:

```json
{
  "status": "UP"
}
```

Detailed health:

```powershell
Invoke-RestMethod -Method Get -Uri "http://localhost:8010/health/details"
```

Equivalent curl:

```bash
curl -s http://localhost:8010/health/details
```

Expected response shape:

```json
{
  "status": "UP",
  "service": "secure-api-gateway",
  "version": "0.1.0",
  "environment": "local",
  "timestamp_utc": "2026-06-30T..."
}
```

The detailed health response must not expose `client_secret`, `api_key`, access tokens, or refresh tokens.

## Validate Phase 3: Wrapper Auth Endpoints

Login through the wrapper:

```powershell
Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8010/auth/login" `
  -ContentType "application/json" `
  -Body '{"username":"raguser","password":"raguser123"}'
```

Equivalent curl:

```bash
curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"raguser","password":"raguser123"}'
```

Expected response shape:

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<refresh-token>",
  "token_type": "Bearer",
  "expires_in": 300,
  "refresh_expires_in": 1800,
  "scope": "profile email"
}
```

Invalid login:

```bash
curl -s -i -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"raguser","password":"wrong"}'
```

Expected HTTP status:

```text
401 Unauthorized
```

Expected response shape:

```json
{
  "error": {
    "code": "invalid_credentials",
    "message": "Invalid username or password.",
    "request_id": "<request-id>"
  }
}
```

Refresh through the wrapper. Replace `<refresh-token>` with the value returned by `/auth/login`:

```bash
curl -s -X POST "http://localhost:8010/auth/refresh" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh-token>"}'
```

Expected response shape:

```json
{
  "access_token": "<new-jwt>",
  "refresh_token": "<new-refresh-token>",
  "token_type": "Bearer"
}
```

Logout through the wrapper. Replace `<refresh-token>` with a valid refresh token:

```bash
curl -s -X POST "http://localhost:8010/auth/logout" \
  -H "Content-Type: application/json" \
  -d '{"refresh_token":"<refresh-token>"}'
```

Expected response:

```json
{
  "status": "LOGGED_OUT"
}
```

## Validate Phase 4: Protected /auth/me

`/auth/me` requires an access token issued by Keycloak. You can get the token from the wrapper login endpoint.

PowerShell:

```powershell
$loginResponse = Invoke-RestMethod `
  -Method Post `
  -Uri "http://localhost:8010/auth/login" `
  -ContentType "application/json" `
  -Body '{"username":"raguser","password":"raguser123"}'

Invoke-RestMethod `
  -Method Get `
  -Uri "http://localhost:8010/auth/me" `
  -Headers @{ Authorization = "Bearer $($loginResponse.access_token)" }
```

Expected response:

```json
{
  "sub": "<keycloak-user-id>",
  "preferred_username": "raguser",
  "email": "raguser@example.local",
  "name": "RAG User",
  "roles": [
    "default-roles-rag-auth-gateway",
    "offline_access",
    "rag_search_user",
    "rag_user",
    "uma_authorization"
  ],
  "issuer": "http://localhost:8080/realms/rag-auth-gateway"
}
```

The exact role list can include Keycloak default realm roles in addition to the application roles.

curl:

```bash
TOKEN=$(curl -s -X POST "http://localhost:8010/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"username":"raguser","password":"raguser123"}' | jq -r .access_token)

curl -s "http://localhost:8010/auth/me" \
  -H "Authorization: Bearer $TOKEN"
```

Missing bearer token:

```bash
curl -s -i "http://localhost:8010/auth/me"
```

Expected HTTP status:

```text
401 Unauthorized
```

Expected response shape:

```json
{
  "error": {
    "code": "missing_bearer_token",
    "message": "Missing bearer token.",
    "request_id": "<request-id>"
  }
}
```

Invalid bearer token:

```bash
curl -s -i "http://localhost:8010/auth/me" \
  -H "Authorization: Bearer invalid-token"
```

Expected HTTP status:

```text
401 Unauthorized
```

Expected response shape:

```json
{
  "error": {
    "code": "invalid_bearer_token",
    "message": "Invalid or expired bearer token.",
    "request_id": "<request-id>"
  }
}
```

## Validate Not-Yet-Implemented Routes

These routes are expected to return `404` until phase 5 is implemented:

```bash
curl -s -i -X POST http://localhost:8010/rag/search -H "Content-Type: application/json" -d '{}'
curl -s -i -X POST http://localhost:8010/rag/ingest -H "Content-Type: application/json" -d '{}'
curl -s -i -X POST http://localhost:8010/rag/ask -H "Content-Type: application/json" -d '{}'
curl -s -i http://localhost:8010/rag/test-downstream
```

Expected status:

```text
404 Not Found
```

## Run Automated Tests

From the repository root:

```powershell
.\.venv\Scripts\python.exe -m pytest modules\secure_api\tests
```

Expected result:

```text
15 passed
```

If you run `pytest` with the global Python installation, dependency imports may fail. Use the repo virtualenv or install:

```powershell
pip install -r .\modules\secure_api\requirements.txt
```

## Troubleshooting

If `/auth/login` returns `401` for valid credentials, check that the wrapper is using:

```text
KEYCLOAK_REALM=rag-auth-gateway
```

If Keycloak token generation fails with `invalid_client`, confirm:

```text
KEYCLOAK_CLIENT_ID=fastapi-auth-gateway
KEYCLOAK_CLIENT_SECRET=fastapi-auth-gateway-secret
```

If discovery or JWKS returns `404`, rerun the Keycloak setup:

```powershell
.\scripts\keycloak\01-keycloak-setup.ps1
```

If the wrapper service does not start, check port `8010` and run:

```powershell
.\modules\secure_api\run_local.ps1
```
