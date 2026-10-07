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
| Add OpenTelemetry Python packages | `modules/rag-answer-service/requirements.txt`<br>`modules/rag-search-service/requirements.txt`<br>`modules/rag-ingest-service/requirements.txt` | Adds the OpenTelemetry distribution and OTLP exporter to each service image. For example, `modules/rag-answer-service/requirements.txt` contains:<br><br><pre>opentelemetry-distro<br>opentelemetry-exporter-otlp</pre> These packages provide the OpenTelemetry SDK, automatic instrumentation, and the OTLP exporter used to send traces, metrics, and logs to the Collector. |
| Instrument the service image | `modules/rag-answer-service/Dockerfile`<br>`modules/rag-search-service/Dockerfile`<br>`modules/rag-ingest-service/Dockerfile` | Runs `opentelemetry-bootstrap -a install` during the image build, then starts Uvicorn through `opentelemetry-instrument`. This automatically instruments supported FastAPI/ASGI, HTTP client, logging, and database libraries. |
| Configure telemetry in Kubernetes | `k8s/rag-answer-service/deployment.yaml`<br>`k8s/rag-search-service/deployment.yaml`<br>`k8s/rag-ingest-service/deployment.yaml` | Stores the nine `OTEL_*` environment variables in the Deployment template. Kubernetes passes them to every replacement pod. These manifests are the source of truth. |
| Keep a manual recovery helper | `scripts/configure-otel-k8s.bat` | Can apply the same variables to a live Deployment when needed, but normal Jenkins deployments use the version-controlled Deployment YAML files. |

The existing Jenkins pipeline builds each service's runtime Docker image and
renders its Deployment YAML with the selected image tag. Therefore, future
deployments retain the OpenTelemetry startup command and environment variables.

### How the service image change works

The dependency entries are installed when the Docker image is built. Then
`opentelemetry-bootstrap -a install` detects supported libraries already
installed in the image and installs their OpenTelemetry instrumentors. At
runtime, the Dockerfile starts the service with `opentelemetry-instrument`
instead of calling Uvicorn directly. This wrapper initializes OpenTelemetry,
applies the installed instrumentors, and starts the same FastAPI application.
The Kubernetes `OTEL_*` environment variables then tell the running wrapper
where to send the collected telemetry.

### Role of `requirements.txt` during the image build

`requirements.txt` is the dependency input for the service image; it is not
executed as a Python program. For the answer service, the Dockerfile performs
these steps during the `base` build stage:

1. `COPY requirements.txt ./requirements.txt` copies the file from the service
   directory into `/app` inside the temporary image build environment.
2. `pip install -r requirements.txt` reads each line and installs the listed
   packages, including `opentelemetry-distro` and
   `opentelemetry-exporter-otlp`, into the Python environment in the image.
3. `opentelemetry-bootstrap -a install` uses those installed packages to add
   the matching automatic instrumentors for libraries such as FastAPI and
   HTTP clients.
4. The completed `base` stage is reused by the `test` and `runtime` stages, so
   the runtime image already contains these dependencies when it starts.

The Docker build process calls the Dockerfile, and the Dockerfile calls `pip`
with `requirements.txt` as its input. In this project, Jenkins starts the
Docker build for each service; Jenkins does not install the Python packages
itself. Package installation happens once while the image is being built, not
when a Kubernetes pod starts. At runtime, the container uses the already
installed packages and starts the application with `opentelemetry-instrument`.

Only the client-side integration lives in this repository. Grafana, Loki,
Tempo, Prometheus, and the Collector are supplied by the separate local
`grafana-lgtm` Docker container, not by the FastAPI service images or Kubernetes
manifests in this project.

## Kubernetes configuration

### How deployment works in this setup

This project uses Docker Desktop's local Kubernetes cluster. It does not use a
container registry for the local deployment. Jenkins builds each selected
service image directly into the local Docker image store, for example:

```text
docker build --target runtime -t rag-answer-service:<image-tag> \
  -f modules/rag-answer-service/Dockerfile modules/rag-answer-service
```

The deployment manifest initially contains `image: __IMAGE__`. The CI worker
replaces that placeholder with the locally built image name and pipes the
result to `kubectl apply`. Because the image is already in Docker Desktop's
image store, the manifest uses `imagePullPolicy: Never`; Kubernetes does not
try to download it from Docker Hub or another registry. Jenkins then waits for
the Deployment rollout to complete.

In a cluster that cannot access the Jenkins or Docker Desktop image store, a
registry is required. The build would then be:

```text
docker build -t registry.example.com/rag/rag-answer-service:<image-tag> ...
docker push registry.example.com/rag/rag-answer-service:<image-tag>
```

The Deployment would reference that pushed image, use an appropriate pull
policy such as `IfNotPresent` or `Always`, and may need an
`imagePullSecrets` entry for a private registry. The current local setup does
not perform the `docker push` step.

#### Manifest files and their responsibilities

Each service directory normally contains these Kubernetes YAML files:

| File | Purpose in this setup |
| --- | --- |
| `deployment.yaml` | Defines the desired Pods, container image, exposed container port, environment variables, health probes, resource limits, and replica count. Applying it creates or updates the service's Pods. |
| `configmap.yaml` | Stores non-sensitive application configuration such as URLs, timeouts, feature flags, and model names. The Deployment loads these values with `envFrom.configMapRef`. |
| `service.yaml` | Creates a stable internal network name and port, such as `http://rag-search-service:8001`. Its selector sends traffic to Pods with the matching `app` label. `ClusterIP` means it is reachable inside the cluster, not directly from the public internet. |
| `secret.yaml` | Stores sensitive values as Kubernetes Secret data. The existing `k8s/secure-api/secret.yaml` is loaded by `secure-api` through `envFrom.secretRef`. The checked-in local file uses `stringData`, so production deployments should use protected secret management rather than committing real credentials. |
| `namespace.yaml` | Creates the `rag-poc` namespace. It provides an isolated naming and management boundary for the application resources. |

The Jenkins pipeline first applies the root `k8s/namespace.yaml`. For each
selected service, the deployment worker applies `configmap.yaml` and, when
present, `secret.yaml`, then applies `service.yaml` and `deployment.yaml`.
The repository also contains `k8s/rag-answer-service/namespace.yaml`, but the
pipeline uses the root namespace manifest as the common source for `rag-poc`.
The existing secret file is named `secret.yaml` (singular), although it serves
the same purpose commonly described as a `secrets.yaml` file.
Applying the files is idempotent: Kubernetes creates a resource if it does
not exist or updates the existing resource to match the manifest.

For production, do not commit real credentials, API keys, database passwords,
or signing keys in `secret.yaml`, ConfigMaps, Helm values, Dockerfiles, or
Jenkins logs. Kubernetes Secret values are only base64-encoded by default, not
automatically encrypted in every storage configuration, so a checked-in
Secret is not safe simply because it uses `stringData` or `data`.

A production deployment should keep secrets in an approved secret manager
such as Azure Key Vault, AWS Secrets Manager, Google Secret Manager, or
HashiCorp Vault. The cluster can load them at deploy or pod startup through an
integration such as External Secrets Operator or the Secrets Store CSI
Driver. Another acceptable GitOps approach is to commit only an encrypted
manifest, using a tool such as Sealed Secrets or SOPS; the decryption key must
remain outside the repository.

The production flow is therefore:

1. An administrator or secret-management process stores the value in the
   external secret manager.
2. A controlled Kubernetes integration syncs the value into a namespaced
   Kubernetes Secret, or mounts it into the Pod as a secret volume.
3. `deployment.yaml` references the Secret with `secretRef` or `secretKeyRef`;
   the application receives the value as an environment variable or mounted
   file without the value appearing in the Deployment manifest.
4. Access is restricted with least-privilege RBAC, and the secret manager
   provides audit records, expiration, and rotation. Rotated values should
   trigger a controlled Pod restart or rollout so applications reload them.

For local development, use an untracked local file or environment variables
and add that file to `.gitignore`. If a real secret is ever committed, remove
it from the repository history and rotate or revoke it immediately; deleting
the latest copy alone does not make the old credential safe.

#### Manifest environment values versus Kubernetes environment variables

There are two related but different concepts:

- A value in `configmap.yaml` or `secret.yaml` is stored as Kubernetes
  configuration data. It does not enter a container until a Pod references
  that ConfigMap or Secret.
- An entry under `spec.template.spec.containers[].env` in `deployment.yaml`
  is an environment variable definition for the container. A direct `value`
  is written into the Pod specification, while `envFrom` imports many values
  from a referenced ConfigMap or Secret.

For example, `RAG_SEARCH_BASE_URL` is defined in the answer service's
ConfigMap and becomes a container environment variable through
`envFrom.configMapRef`. The OpenTelemetry settings such as
`OTEL_EXPORTER_OTLP_ENDPOINT` are defined directly in `deployment.yaml`, so
Kubernetes places them into the Pod environment when it creates the
container. The application then reads both types through its normal process
environment; the source is different, but the application-facing result is
the same.

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

## LGTM Docker image

This local setup uses the `grafana/otel-lgtm:latest` Docker image. LGTM groups
four observability components: Loki for logs, Grafana for dashboards and
alerting, Tempo for distributed traces, and Prometheus-compatible metrics
storage (Prometheus in this image; Mimir can be used as an alternative in a
larger deployment). The image also includes the OpenTelemetry Collector, which
receives OTLP traffic from the services and routes each signal to the matching
backend. Start the container with ports `3000` (Grafana) and `4318` (OTLP over
HTTP) available; `host.docker.internal` is used by the local Kubernetes pods to
reach the Collector.
