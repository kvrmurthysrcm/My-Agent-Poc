# Online Library API POC

Read-only FastAPI module for exposing Online Library catalog data and selected database tables as JSON.

## Run

```powershell
.\.venv\Scripts\python.exe -m uvicorn modules.online_library.api:app --reload --port 8003
```

From the repository root, or by double-clicking from this module folder, you can also use:

```powershell
modules\online_library\run-library-api-service.bat
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

Catalog search endpoints:

- `GET /catalog/resources`
- `GET /catalog/resources/{resource_id}`
- `GET /catalog/facets`

`GET /catalog/resources` supports structured metadata search:

```text
?q=frankenstein&author=Mary&genre=Gothic&tag=classic&tier=FREE&limit=20&offset=0&sort=title
```

Supported filters:

- `q`
- `author`
- `category`
- `genre` alias for category
- `tag`
- `publisher`
- `language`
- `tier`
- `status`
- `published_from`
- `published_to`
- `limit`
- `offset`
- `sort`

Supported sort values:

- `title`
- `created_desc`
- `created_asc`
- `published_desc`
- `published_asc`

Catalog responses exclude binary content and include joined metadata arrays:

- `authors`
- `tags`
- `category`
- `genre`

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

## Postman Validation

Import:

```text
modules/online_library/postman/Online_Library.postman_collection.json
```

Collection variables:

- `baseUrl`: defaults to `http://127.0.0.1:8003`
- `resourceId`: set this after running `Catalog - List Resources`

Recommended validation order:

1. Run `Health - DB`.
2. Run `Catalog Search / Catalog - Facets`.
3. Run `Catalog Search / Catalog - List Resources`.
4. Copy any returned `resource_id` into the `resourceId` collection variable.
5. Run `Catalog Search / Catalog - Resource Detail`.
6. Run filter examples:
   - `Catalog - Search by Text`
   - `Catalog - Search by Author`
   - `Catalog - Search by Genre`
   - `Catalog - Search by Tag`
   - `Catalog - Filter by Tier and Status`

Expected catalog response behavior:

- `authors` and `tags` are arrays.
- `category` and `genre` are both present.
- Binary fields such as `file_content` and `preview_content` are not returned.
