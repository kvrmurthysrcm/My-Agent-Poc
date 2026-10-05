# Step 10 — Instrument Search Service

Use the working Answer implementation as the reference.

Apply the same validated pattern to rag-search-service:
- OTEL_SERVICE_NAME=rag-search-service
- same OTel dependencies/bootstrap
- same `opentelemetry-instrument` startup
- same OTLP endpoint/protocol/resource attributes

Do incrementally:
inspect -> dependencies -> Docker -> build -> Deployment env -> deploy -> startup check -> connectivity -> invoke Search -> confirm in Tempo.

Do not modify Ingest yet. Report every changed file and differences from Answer.
