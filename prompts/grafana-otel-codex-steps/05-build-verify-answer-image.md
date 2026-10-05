# Step 5 — Build and Verify Answer Image

Build only rag-answer-service using the existing project build/tag convention. Do not deploy.

Verify inside the image:
- `opentelemetry-instrument --help`
- `opentelemetry-bootstrap --help`

Inspect installed instrumentation for libraries actually used, such as FastAPI/Uvicorn/httpx/requests/SQLAlchemy/Redis/PostgreSQL.

Report image name/tag, build result, OTel packages, instrumentation packages, warnings/errors.
