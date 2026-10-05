# Step 12 — Instrument Ingest Service

Apply the proven pattern to rag-ingest-service.

Use:
`OTEL_SERVICE_NAME=rag-ingest-service`

Perform:
dependency update -> Docker build update -> instrumented startup -> Deployment OTEL env -> rebuild -> deploy -> connectivity -> invoke normal ingest API -> verify in Tempo.

Avoid unrelated refactoring.

Summarize final OTel configuration across all three services.
