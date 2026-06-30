# Keycloak Setup for FastAPI Auth Gateway

This phase creates the Keycloak resources needed by the future FastAPI wrapper service. It does not create any FastAPI files.

## Local Settings

| Setting | Value |
| --- | --- |
| Keycloak URL | `http://localhost:8080` |
| Docker container | `local-keycloak` |
| Admin user | `admin` |
| Realm | `rag-auth-gateway` |
| Client ID | `fastapi-auth-gateway` |
| Wrapper URL | `http://localhost:8010` |
| Access token lifespan | `604800` seconds / 7 days |

The local POC passwords and 7-day JWT lifespan are stored in the scripts because this is a development-only laptop setup. Do not use these values in production.

## Created Realm Roles

- `rag_user`
- `rag_admin`
- `rag_search_user`
- `rag_ingest_user`
- `graph_rag_user`
- `system_admin`

## Created Users

| Username | Password | Roles |
| --- | --- | --- |
| `raguser` | `raguser123` | `rag_user`, `rag_search_user` |
| `ragadmin` | `ragadmin123` | `rag_admin`, `rag_user`, `rag_search_user`, `rag_ingest_user`, `graph_rag_user`, `system_admin` |
| `searchuser` | `searchuser123` | `rag_search_user` |

## Run Setup

From the repository root:

```powershell
.\scripts\keycloak\01-keycloak-setup.ps1
```

The setup script uses:

```text
docker exec local-keycloak /opt/keycloak/bin/kcadm.sh
```

It is idempotent for normal local POC use: it creates missing resources and updates the client, users, passwords, and role assignments.

The setup script also configures these realm token/session values for local testing:

```text
accessTokenLifespan=604800
ssoSessionIdleTimeout=604800
ssoSessionMaxLifespan=604800
clientSessionIdleTimeout=604800
clientSessionMaxLifespan=604800
```

## Configure Only 7-Day JWT Lifespan

If the realm already exists and you only want to reapply the local 7-day JWT/session settings, run:

```powershell
.\scripts\keycloak\03-keycloak-token-lifespan-7-days.ps1
```

The script runs this Keycloak admin CLI command inside the `local-keycloak` container:

```text
docker exec local-keycloak /opt/keycloak/bin/kcadm.sh update realms/rag-auth-gateway --no-config --server http://localhost:8080 --realm master --user admin --password admin123 -s accessTokenLifespan=604800 -s ssoSessionIdleTimeout=604800 -s ssoSessionMaxLifespan=604800 -s clientSessionIdleTimeout=604800 -s clientSessionMaxLifespan=604800
```

## Verify Setup

From the repository root:

```powershell
.\scripts\keycloak\02-keycloak-verify.ps1
```

The verification script checks:

- Discovery URL
- JWKS URL
- Password-grant token generation for `raguser`
- Password-grant token generation for `ragadmin`
- Password-grant token generation for `searchuser`
- Access token `exp - iat` is about `604800` seconds / 7 days

It prints only the first 30 characters of each access token.

## Important URLs

```text
Issuer:
http://localhost:8080/realms/rag-auth-gateway

Discovery:
http://localhost:8080/realms/rag-auth-gateway/.well-known/openid-configuration

Token:
http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/token

JWKS:
http://localhost:8080/realms/rag-auth-gateway/protocol/openid-connect/certs
```

## Troubleshooting

If setup fails, confirm the container is running:

```powershell
docker ps --filter "name=local-keycloak"
```

If admin login fails, confirm `admin / admin123` works in the Keycloak admin console.

If token generation fails, confirm the client has direct access grants enabled and the user password is not temporary.
