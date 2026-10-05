# Step 05 - Build and Verify Answer Image Report

**Status:** Completed successfully  
**Run date:** 2026-10-04  
**Scope:** Built and inspected the Answer runtime image only. No image was deployed, no Kubernetes resource changed, and no application process was started.

## Build result

| Field | Value |
| --- | --- |
| Image | rag-answer-service:local |
| Build target | runtime |
| Build command | docker build --target runtime -t rag-answer-service:local -f modules\rag-answer-service\Dockerfile modules\rag-answer-service |
| Result | Passed, exit code 0 |
| Image ID | sha256:4f73e2b2a04a7738a912f7c2be8f645e73264ce66f65dfc64bc8ec7dc3f2fc64 |
| Image size | 74,177,707 bytes (about 70.74 MiB) |
| Deployed image | Unchanged; rag-answer-service still runs rag-answer-service:46-61072fb in Kubernetes. |

The local tag follows the project’s existing manual build convention. It did not replace the deployed 46-61072fb tag.

## Required CLI verification

Both commands ran successfully in temporary auto-removed containers:

~~~text
docker run --rm --entrypoint opentelemetry-instrument rag-answer-service:local --help
docker run --rm --entrypoint opentelemetry-bootstrap rag-answer-service:local --help
~~~

Results:

- opentelemetry-instrument is installed and documents OTLP endpoint/protocol options, including the settings supplied to the live Answer Deployment in Step 03.
- opentelemetry-bootstrap is installed and supports the required -a install action.
- No verification containers remain after the checks.

## Installed OTel packages

| Package | Installed version |
| --- | --- |
| opentelemetry-api | 1.45.0 |
| opentelemetry-sdk | 1.45.0 |
| opentelemetry-distro | 0.66b0 |
| opentelemetry-exporter-otlp | 1.45.0 |
| opentelemetry-exporter-otlp-proto-http | 1.45.0 |
| opentelemetry-exporter-otlp-proto-grpc | 1.45.0 |
| opentelemetry-instrumentation | 0.66b0 |

The presence of opentelemetry-exporter-otlp-proto-http confirms support for the planned OTLP HTTP/protobuf configuration.

## Instrumentation inspection

The build-time bootstrap detected and installed the following relevant packages:

| Library or runtime path | Installed instrumentation |
| --- | --- |
| FastAPI | opentelemetry-instrumentation-fastapi 0.66b0 |
| ASGI / Starlette | opentelemetry-instrumentation-asgi 0.66b0; opentelemetry-instrumentation-starlette 0.66b0 |
| HTTPX | opentelemetry-instrumentation-httpx 0.66b0 |
| Python logging | opentelemetry-instrumentation-logging 0.66b0 |
| OpenAI client | opentelemetry-instrumentation-openai-v2 2.4b0 |

The bootstrap output also installed general or transitively detected instrumentations, including asyncio, DBAPI, exceptions, gRPC, SQLite, threading, urllib, urllib3, WSGI, and Tortoise ORM.

There is no Uvicorn-specific instrumentation package in the image; the FastAPI/ASGI instrumentation is the relevant inbound-server coverage for this Uvicorn-hosted application. Answer does not directly use requests, SQLAlchemy, Redis, psycopg, or PostgreSQL, so matching instrumentation packages for those libraries are not expected for this service.

## Runtime command verification

The image configuration remains intentionally unchanged:

~~~text
Cmd=["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8002"]
Entrypoint=null
~~~

This is correct for Step 05. Step 06 will change the effective runtime command to start through opentelemetry-instrument.

## Validation performed

| Validation | Result |
| --- | --- |
| Runtime Docker build | Passed |
| opentelemetry-instrument --help inside built image | Passed |
| opentelemetry-bootstrap --help inside built image | Passed |
| Bootstrap detected instrumentation requirements | Passed |
| Installed OTel package inventory | Passed |
| pip check inside built image | Passed: No broken requirements found. |
| Effective image CMD / Entrypoint inspection | Passed; direct Uvicorn command is preserved. |
| Deployment or Kubernetes mutation | Not performed. |

## Test-run details

No unit tests or test-image build were run. Step 05 requested the runtime-image build and installed-package verification only. No container was started with the application CMD, and no traffic was sent to Tempo or Grafana.

## Warnings and observations

1. The mandatory bootstrap command installs more instrumentation packages than Answer directly needs. This is expected from automatic library detection, but it increases the local image footprint.
2. The requirements use floating versions, so the verified package versions reflect this build date. Pin or lock versions before treating this image as a reproducible production artifact.
3. The built image is local only. The live Answer pod remains on the prior image and will not emit OpenTelemetry data until Steps 06 and 07 are approved and completed.

## Next decision gate

Step 05 is complete. Approve Step 06 to change only the Answer image's effective startup command to run through opentelemetry-instrument; do not deploy it yet.
