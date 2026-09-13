# Authentication and Authorization

## WHAT

`AuthService` owns login, registration, session restoration, tokens, `/auth/me`, refresh, logout, and role helpers. Functional guards and navigation visibility consume the same role state.

## WHY

Authentication state must not be scattered through page components. A single service also lets a future BFF/cookie session replace local storage with minimal feature changes.

## HOW

```text
Login -> POST /auth/login -> TokenStorage -> GET /auth/me -> signal(CurrentUser)
Request -> auth interceptor -> bearer token -> gateway
401 -> one shared refresh Observable -> retry once -> clear/navigate login on failure
```

The POC faithfully retains `secure_api_access_token` and `secure_api_refresh_token` local-storage keys. The interceptor does not attach tokens to non-`/api` URLs, skips login/refresh/logout, and preserves browser-managed multipart boundaries.

| Role | UI capability examples |
| --- | --- |
| ordinary authenticated user | Books, catalog, Library Search |
| `rag_search_user` / `rag_user` | Content search |
| `rag_ingest_user` | Ingestion/job polling |
| `rag_user` | Answer and comparison |
| `rag_admin` / `system_admin` | Resource administration, raw library tools |

Route guards and hidden links improve the experience only. The gateway independently validates JWTs and role requirements on every protected endpoint.

## Production recommendation

Prefer a backend-for-frontend session with Secure, HttpOnly, SameSite cookies, short-lived server-side tokens, CSP, XSS prevention, rotation, and logout/revocation policy. Do not treat client JWT decoding or a client role check as security.

## Interview takeaway

Use an interceptor for token attachment and a shared single-flight refresh stream to prevent refresh storms. Explain that a SPA guard is navigation policy, not an authorization boundary.
