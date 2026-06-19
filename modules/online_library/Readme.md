# Online Library API POC

Read-only FastAPI module for exposing non-empty Online Library database tables as JSON.

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.online_library.api:app --reload --port 8003
```

Open:

```text
http://127.0.0.1:8003/docs
```

## Configuration

Defaults match the local POC database:

```env
ONLINE_LIBRARY_DB_HOST=localhost
ONLINE_LIBRARY_DB_PORT=5432
ONLINE_LIBRARY_DB_NAME=online_library
ONLINE_LIBRARY_DB_USER=library_user
ONLINE_LIBRARY_DB_PASSWORD=library_pass
```

## Endpoints

Only tables with rows at implementation time are exposed.

Empty tables not exposed:

- `audit_log`
- `downloads`
- `reviews`

Read endpoints:

- `GET /health/db`
- `GET /tables`
- `GET /authors`
- `GET /categories`
- `GET /library-users`
- `GET /reading-progress`
- `GET /resource-authors`
- `GET /resource-tags`
- `GET /resources`
- `GET /subscription-rules`
- `GET /subscription-tiers`
- `GET /tags`
- `GET /user-approval-requests`
- `GET /user-bookshelf`
- `GET /user-subscriptions`

Table endpoints support:

```text
?limit=20&offset=0
```
