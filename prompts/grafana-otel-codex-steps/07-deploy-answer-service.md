# Step 7 — Deploy Instrumented Answer Service

Rebuild and deploy only rag-answer-service with the project's normal local Docker Desktop Kubernetes process.

Verify:
1. Kubernetes uses the newly built image.
2. Existing OTEL_* Deployment variables remain.
3. Rollout succeeds and pod is Ready.
4. Pod logs show no obvious exporter/startup errors.
5. `opentelemetry-instrument` exists inside the pod.
6. Effective process command contains `opentelemetry-instrument`.

Report image/tag, pod, status, effective command, OTEL values, logs/errors.
