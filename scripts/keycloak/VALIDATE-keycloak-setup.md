# Validate Keycloak Setup

Use this guide after running:

```powershell
.\scripts\keycloak\01-keycloak-setup.ps1
```

## 1. Confirm Keycloak Container Is Running

```powershell
docker ps --filter "name=local-keycloak"
```

Expected:

- Container name is `local-keycloak`
- Port `8080` is mapped
- Status is `Up`

## 2. Run the Verification Script

From the repository root:

```powershell
.\scripts\keycloak\02-keycloak-verify.ps1
```

Expected successful output includes:

```text
Checking discovery document...
  OK: http://localhost:8080/realms/rag-auth-gateway/.well-known/openid-configuration
Checking JWKS document...
  OK: http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/certs

Requesting user tokens...
  OK: raguser received access_token with expected realm roles and 7-day lifespan: eyJhbGciOiJSUzI1NiIsInR5cCIgOi...
  OK: ragadmin received access_token with expected realm roles and 7-day lifespan: eyJhbGciOiJSUzI1NiIsInR5cCIgOi...
  OK: searchuser received access_token with expected realm roles and 7-day lifespan: eyJhbGciOiJSUzI1NiIsInR5cCIgOi...

Keycloak verification complete.
```

The script validates:

- Discovery endpoint is reachable
- JWKS endpoint is reachable
- Password grant works for all POC users
- Access tokens are returned
- Tokens contain expected `realm_access.roles`
- Access token `exp - iat` is about `604800` seconds / 7 days
- Full JWTs are not printed

## Reapply 7-Day Local JWT Lifespan

If tokens are expiring too quickly, run:

```powershell
.\scripts\keycloak\03-keycloak-token-lifespan-7-days.ps1
```

Expected values after the script runs:

```text
accessTokenLifespan:       604800
ssoSessionIdleTimeout:     604800
ssoSessionMaxLifespan:     604800
clientSessionIdleTimeout:  604800
clientSessionMaxLifespan:  604800
```

This is only for the local laptop POC.

## 3. Validate URLs Manually

Open these URLs in a browser or call them with `Invoke-RestMethod`.

Discovery:

```text
http://localhost:8080/realms/rag-auth-gateway/.well-known/openid-configuration
```

JWKS:

```text
http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/certs
```

Expected:

- Discovery returns JSON with issuer and endpoint metadata
- JWKS returns JSON with at least one signing key

## 4. Validate Token Generation Manually

Use this command to request a token for `raguser`:

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

````CURL command to test on postman
curl -X POST "http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "grant_type=password" \
     -d "client_id=fastapi-auth-gateway" \
     -d "client_secret=fastapi-auth-gateway-secret" \
     -d "username=raguser" \
     -d "password=raguser123" \
     -d "scope=openid profile email"
````     


Expected:

- Response contains `access_token`
- Response contains `refresh_token`
- Response contains `token_type` with value `Bearer`

Repeat with:

| Username | Password |
| --- | --- |
| `raguser` | `raguser123` |
| `ragadmin` | `ragadmin123` |
| `searchuser` | `searchuser123` |

## 5. Validate in Keycloak Admin Console

Open:

```text
http://localhost:8080/admin
```

Login:

```text
admin / admin123
```

Check:

- Realm exists: `rag-auth-gateway`
- Client exists: `fastapi-auth-gateway`
- Client is confidential
- Direct access grants are enabled
- Standard flow is enabled
- Users exist:
  - `raguser`
  - `ragadmin`
  - `searchuser`
- Realm roles exist:
  - `rag_user`
  - `rag_admin`
  - `rag_search_user`
  - `rag_ingest_user`
  - `graph_rag_user`
  - `system_admin`

## Troubleshooting

If token generation fails with `invalid_client`, check the client secret:

```text
fastapi-auth-gateway-secret
```

If token generation fails with `invalid_grant`, rerun:

```powershell
.\scripts\keycloak\01-keycloak-setup.ps1
```

If discovery or JWKS fails, confirm the realm name is:

```text
rag-auth-gateway
```
