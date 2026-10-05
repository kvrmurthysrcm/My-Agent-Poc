# Grafana LGTM + OpenTelemetry — Execution Details

Context:
- Python FastAPI services run as Kubernetes pods in Docker Desktop on Windows.
- Grafana LGTM runs as a separate Docker container.
- Grafana: http://localhost:3000
- OTLP HTTP: http://host.docker.internal:4318
- Services: rag-answer-service, rag-search-service, rag-ingest-service.


## Goal
Implement observability incrementally and isolate failures by layer instead of changing all services at once.

## Target flow

```text
rag-answer / rag-search / rag-ingest (Kubernetes pods)
          |
          | OTLP HTTP/protobuf
          v
host.docker.internal:4318
          |
          v
grafana-lgtm container
   |       |       |
 Tempo    Loki   Prometheus
          |
        Grafana :3000
```

## Standard Deployment environment

```text
OTEL_SERVICE_NAME=<service>
OTEL_RESOURCE_ATTRIBUTES=service.namespace=rag-poc,deployment.environment=local
OTEL_EXPORTER_OTLP_ENDPOINT=http://host.docker.internal:4318
OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf
OTEL_TRACES_EXPORTER=otlp
OTEL_METRICS_EXPORTER=otlp
OTEL_LOGS_EXPORTER=otlp
OTEL_PYTHON_LOG_CORRELATION=true
OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=click
```

Do not use `localhost:4318` inside a pod; that points to the pod itself.

`click` must remain disabled for these Uvicorn services. The auto-installed
Click instrumentor otherwise keeps Uvicorn's long-running CLI command as the
active span, which prevents inbound ASGI instrumentation from extracting W3C
trace context.

## Execution order

1. `01-inspect-otel-readiness.md`
   - inventory only; no changes.

2. `02-add-configure-otel-batch.md`
   - create/review `scripts/configure-otel-k8s.bat`.

3. `03-validate-otel-script.md`
   - apply OTEL variables to Answer only.
   - a pod restart with no traces yet is acceptable.

4. `04-add-otel-dependencies-answer.md`
   - add OTel packages/bootstrap to Answer image only.

5. `05-build-verify-answer-image.md`
   - build but do not deploy.
   - prove `opentelemetry-instrument` exists.

6. `06-instrument-answer-startup.md`
   - change effective runtime command.
   - check K8s command/args overrides.

7. `07-deploy-answer-service.md`
   - deploy Answer only and verify Ready state.

8. `08-verify-pod-lgtm-connectivity.md`
   - prove pod -> `host.docker.internal:4318`.

9. `09-verify-first-tempo-trace.md`
   - prove a real Answer trace in Tempo.

10. `10-instrument-search-service.md`
    - repeat the validated pattern for Search.

11. `11-verify-distributed-trace.md`
    - prove one Answer -> Search TraceId.

12. `12-instrument-ingest-service.md`
    - repeat for Ingest.

13. `13-evaluate-otel-log-export.md`
    - only after tracing works, evaluate Loki log export/correlation.

## Critical checkpoint: distributed tracing

Expected Tempo hierarchy:

```text
ONE TRACE
|
+-- rag-answer-service server span
    |
    +-- outbound HTTP client span
        |
        +-- rag-search-service server span
```

If Answer and Search produce separate TraceIds, inspect `traceparent` propagation and HTTP client/server instrumentation before writing custom tracing code.

## Troubleshooting order

Always check in this order:

1. Does the pod start?
2. Are OTEL_* variables present?
3. Is `opentelemetry-instrument` installed?
4. Is the effective startup command instrumented?
5. Can the pod reach `host.docker.internal:4318`?
6. Is `grafana-lgtm` running?
7. Do application/collector logs show exporter errors?
8. Does Tempo receive traces?
9. Does Answer -> Search preserve one TraceId?
10. Do logs/metrics export correctly?

## Useful commands

```powershell
docker ps
docker logs --tail 200 grafana-lgtm
docker logs -f grafana-lgtm

kubectl get deployments -A
kubectl get pods -A
kubectl get services -A
kubectl describe deployment <deployment> -n <namespace>
kubectl logs <pod> -n <namespace>
kubectl set env deployment/<deployment> -n <namespace> --list
kubectl exec <pod> -n <namespace> -- env
```

## Later phases

After traces and logs:

14. Metrics / Prometheus
- inspect actual metric names first
- request rate
- errors
- p50/p95/p99 latency
- dependency latency
- runtime/process metrics

15. Grafana dashboards
- request rate
- error rate
- latency
- service breakdown
- downstream latency

16. Alerts
- start with a simple metrics alert
- use low thresholds only for local testing
- verify Normal -> Pending -> Firing -> Normal

## Rollback

If instrumentation breaks a service:
1. restore the previous startup command/image
2. rebuild/redeploy only that service
3. keep the other services unchanged
4. diagnose before proceeding

## Suggested project layout

```text
project-root/
+-- scripts/
|   +-- configure-otel-k8s.bat
+-- docs/
    +-- observability/
        +-- execution-details.md
        +-- codex/
            +-- 01-...md through 13-...md
```

## Completion criteria

The initial lab is successful when:
- all three services appear in Tempo
- Answer -> Search is one distributed trace
- logs can be correlated to traces
- useful Prometheus metrics exist
- at least one dashboard is useful
- at least one local alert can be triggered and recover
