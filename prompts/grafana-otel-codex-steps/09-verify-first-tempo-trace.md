# Step 9 — Verify First Tempo Trace

Validate tracing for rag-answer-service only.

1. Find an existing safe API endpoint.
2. Invoke it several times.
3. Inspect app logs for exporter errors.
4. Inspect grafana-lgtm logs.
5. In Grafana -> Explore -> Tempo, search for:
   `service.name = rag-answer-service`

Report endpoint, HTTP result, whether spans exported, whether trace is visible, child spans seen, and missing instrumentation.

Stop after proving or diagnosing Answer tracing.
