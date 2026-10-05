# Step 3 — Validate OTel Script Safely

Do not change application code or Docker images.

1. Run `kubectl get deployments -A`.
2. Identify the real rag-answer Deployment and namespace.
3. Run `scripts/configure-otel-k8s.bat` only for rag-answer-service.
4. Verify the Deployment received all OTEL_* values.
5. Wait for rollout.
6. Run `kubectl get pods -n <namespace>`.
7. Inspect the new pod environment.
8. Confirm:
   OTEL_SERVICE_NAME, OTEL_RESOURCE_ATTRIBUTES,
   OTEL_EXPORTER_OTLP_ENDPOINT, OTEL_EXPORTER_OTLP_PROTOCOL,
   OTEL_TRACES_EXPORTER, OTEL_METRICS_EXPORTER,
   OTEL_LOGS_EXPORTER, OTEL_PYTHON_LOG_CORRELATION.

Report commands, deployment, namespace, rollout, values, warnings/errors.
