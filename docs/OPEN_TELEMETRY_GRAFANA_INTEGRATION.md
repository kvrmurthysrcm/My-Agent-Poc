# OpenTelemetry and Grafana Integration

## Purpose

The three RAG FastAPI services now send traces, metrics, and logs to the local
Grafana LGTM observability stack. The configuration is stored in the repository
Dockerfiles and Kubernetes manifests, so it can be committed and recreated by a
Jenkins build and Kubernetes deployment.

This document describes the implemented runtime integration only. It does not
cover the diagnostic work used to validate it.

## What changed

No FastAPI endpoints or business logic were changed. Each service image now
contains OpenTelemetry, and each Kubernetes Deployment supplies the OpenTelemetry
configuration when its pod starts.

| Change | Affected files | What it does |
| --- | --- | --- |
| Add OpenTelemetry Python packages | `modules/rag-answer-service/requirements.txt`<br>`modules/rag-search-service/requirements.txt`<br>`modules/rag-ingest-service/requirements.txt` | Adds the OpenTelemetry distribution and OTLP exporter to each service image. |
| Instrument the service image | `modules/rag-answer-service/Dockerfile`<br>`modules/rag-search-service/Dockerfile`<br>`modules/rag-ingest-service/Dockerfile` | Runs `opentelemetry-bootstrap -a install` during the image build, then starts Uvicorn through `opentelemetry-instrument`. This automatically instruments supported FastAPI/ASGI, HTTP client, logging, and database libraries. |
| Configure telemetry in Kubernetes | `k8s/rag-answer-service/deployment.yaml`<br>`k8s/rag-search-service/deployment.yaml`<br>`k8s/rag-ingest-service/deployment.yaml` | Stores the nine `OTEL_*` environment variables in the Deployment template. Kubernetes passes them to every replacement pod. These manifests are the source of truth. |
| Keep a manual recovery helper | `scripts/configure-otel-k8s.bat` | Can apply the same variables to a live Deployment when needed, but normal Jenkins deployments use the version-controlled Deployment YAML files. |

The existing Jenkins pipeline builds each service's runtime Docker image and
renders its Deployment YAML with the selected image tag. Therefore, future
deployments retain the OpenTelemetry startup command and environment variables.

Only the client-side integration lives in this repository. Grafana, Loki,
Tempo, Prometheus, and the Collector are supplied by the separate local
`grafana-lgtm` Docker container, not by the FastAPI service images or Kubernetes
manifests in this project.

## Kubernetes configuration

Each RAG Deployment contains the following settings. The service name changes
per service; the remaining settings are shared.

| Setting | Purpose |
| --- | --- |
| `OTEL_SERVICE_NAME` | Names the service in Grafana: `rag-answer-service`, `rag-search-service`, or `rag-ingest-service`. |
| `OTEL_RESOURCE_ATTRIBUTES` | Adds `service.namespace=rag-poc` and `deployment.environment=local` to all telemetry. |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | Sends telemetry to `http://host.docker.internal:4318`, the Docker Desktop host address reachable from a Kubernetes pod. |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | Uses OTLP over HTTP/protobuf. |
| `OTEL_TRACES_EXPORTER` | Enables trace export. |
| `OTEL_METRICS_EXPORTER` | Enables metric export. |
| `OTEL_LOGS_EXPORTER` | Enables log export. |
| `OTEL_PYTHON_LOG_CORRELATION` | Adds OpenTelemetry trace and span context to Python log records. |
| `OTEL_PYTHON_DISABLED_INSTRUMENTATIONS` | Disables Click instrumentation. This avoids an unwanted long-running Uvicorn command span and keeps incoming request trace links correct. |

`host.docker.internal:4318` is specific to this local Docker Desktop setup. A
remote Kubernetes cluster must use the address of its own OpenTelemetry
Collector instead.

## How data reaches Grafana

```text
FastAPI service pod
  |-- traces, metrics, logs over OTLP HTTP/protobuf
  v
host.docker.internal:4318
  v
OpenTelemetry Collector in grafana-lgtm
  |-- traces  -> Tempo
  |-- logs    -> Loki
  |-- metrics -> Prometheus
  v
Grafana UI at http://localhost:3000
```

The local `grafana/otel-lgtm:latest` container runs Grafana, the OpenTelemetry
Collector, Loki, Tempo, Prometheus, and Pyroscope. Prometheus is already
included in this observability container; it is not installed in the three
FastAPI service images.

## Logs: source and live viewing

The applications use Python's standard `logging` package. Their existing
configuration writes log records to standard output, so `kubectl logs` remains
available. The OpenTelemetry logging auto-instrumentation also exports the same
records through OTLP to the Collector, whose logs pipeline sends them to Loki.

Log records include service resource information such as `service_name`,
`service_namespace`, and `deployment_environment`. They also contain OTel
fields such as `otelTraceID` and `otelSpanID`, which are the fields to use when
linking a Loki log to a Tempo trace. The project also has its older application
`trace_id`, `span_id`, and `request_id` fields; they are useful context but are
not always the same as the OpenTelemetry trace and span IDs.

To view live logs:

1. Open [Grafana](http://localhost:3000) in a browser and sign in with the
   credentials configured for the local LGTM container.
2. Open **Explore** and select the **Loki** data source.
3. Start with a service query such as `{service_name="rag-answer-service"}`.
4. Open a log line to inspect its structured fields, or filter by its
   `otelTraceID` to find related log records.

For a terminal view of the same pod output, use:

```powershell
kubectl logs deployment/rag-answer-service -n rag-poc -f

kubectl -n rag-poc logs deployment/rag-answer-service --since=30m

```

## Metrics and Prometheus

`OTEL_METRICS_EXPORTER=otlp` sends metrics emitted by the OpenTelemetry SDK and
its automatic instrumentors to the Collector. The Collector forwards them to
the Prometheus server inside `grafana-lgtm` using its OTLP receiver. No
Prometheus package, sidecar, or server must be added to the FastAPI images.

To view metrics:

1. Open **Explore** in Grafana and select the **Prometheus** data source.
2. Use the metric browser to see the metric names currently emitted by the
   services.
3. Start with `up`, then inspect HTTP, process, runtime, and collector metrics.
   Where present, filter service metrics with `service_name="rag-search-service"`
   or another service name.

Automatic instrumentation provides technical telemetry. Application-specific
business metrics, such as documents indexed or answer quality, have not been
added and would require explicit metric code in the relevant service.

## Traces

Open **Explore**, select the **Tempo** data source, and search by service name.
For example, choose `rag-answer-service` to inspect incoming HTTP spans and the
outbound call to Search. Grafana can use the `otelTraceID` on a Loki log to open
the related trace when the data source links are available.

## Prometheus in another environment

For this local environment, no additional Prometheus installation is needed.
For another cluster, deploy or use a Prometheus-compatible metrics backend and
configure that environment's OpenTelemetry Collector to forward OTLP metrics to
it. Keep the service images unchanged; change the Collector endpoint and the
Kubernetes `OTEL_EXPORTER_OTLP_ENDPOINT` value for that environment.
