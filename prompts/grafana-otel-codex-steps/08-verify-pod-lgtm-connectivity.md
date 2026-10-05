# Step 8 — Verify Pod to LGTM Connectivity

From the rag-answer pod, verify:
- DNS resolution of `host.docker.internal`
- connectivity to port 4318
- endpoint `http://host.docker.internal:4318`

Use tools already present in the container; do not permanently install debug tools.

Inspect `grafana-lgtm` Docker logs for OTLP activity/errors.

If connectivity fails, diagnose the smallest local-only fix. Do not redesign the architecture unless necessary.

Report DNS, port/connectivity, collector observations, exact errors.
