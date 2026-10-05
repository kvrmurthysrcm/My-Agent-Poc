# Step 04 - Add OpenTelemetry Dependencies to Answer Report

**Status:** Completed successfully  
**Run date:** 2026-10-04  
**Scope:** Updated only the Answer service dependency declaration and Docker build path. This report was created as requested. No image was built, no pod was modified, no package was installed into a running pod, and the runtime startup command was not changed.

## Dependency-management style

The Answer Dockerfile and local launcher both install modules/rag-answer-service/requirements.txt with pip. The Docker image does not run uv sync or install from pyproject.toml/uv.lock, so requirements.txt is the active runtime dependency source.

The change therefore updates requirements.txt and the Answer Dockerfile only. pyproject.toml and uv.lock remain untouched because they are not consumed by the Docker build in the established delivery path.

## Changed files

| File | Change |
| --- | --- |
| modules/rag-answer-service/requirements.txt | Added opentelemetry-distro and opentelemetry-exporter-otlp. |
| modules/rag-answer-service/Dockerfile | Runs opentelemetry-bootstrap -a install after the normal pip dependency installation in the shared base stage. |

## Why these dependencies were added

- opentelemetry-distro supplies the OpenTelemetry distribution and the opentelemetry-instrument executable required for automatic instrumentation.
- opentelemetry-exporter-otlp supplies OTLP exporter support. The already-applied OTEL_EXPORTER_OTLP_PROTOCOL=http/protobuf and OTEL_EXPORTER_OTLP_ENDPOINT settings will select the planned Docker Desktop LGTM HTTP endpoint once the instrumented image is deployed.

## Bootstrap location and expected behavior

The bootstrap command is part of the base Docker stage:

~~~dockerfile
RUN python -m pip install --upgrade pip \
    && pip install -r requirements.txt \
    && opentelemetry-bootstrap -a install
~~~

It runs only during a future Docker image build, after the normal dependencies are present. Because both the test and runtime stages inherit from base, the resulting image stages receive the installed instrumentation packages.

At build time, opentelemetry-bootstrap -a install will inspect installed libraries and install matching instrumentation packages. For this service, the expected automatic-instrumentation coverage includes the FastAPI/ASGI server path, Uvicorn, and HTTPX outbound calls. It does not start instrumentation by itself; Step 06 will change the runtime command to invoke the process through opentelemetry-instrument.

## Diff

~~~diff
diff --git a/modules/rag-answer-service/Dockerfile b/modules/rag-answer-service/Dockerfile
index 59db520..c86a2a1 100644
--- a/modules/rag-answer-service/Dockerfile
+++ b/modules/rag-answer-service/Dockerfile
@@ -14,7 +14,8 @@ RUN apt-get update \
 
 COPY requirements.txt ./requirements.txt
 RUN python -m pip install --upgrade pip \
-    && pip install -r requirements.txt
+    && pip install -r requirements.txt \
+    && opentelemetry-bootstrap -a install
 
 FROM base AS test
diff --git a/modules/rag-answer-service/requirements.txt b/modules/rag-answer-service/requirements.txt
index d86dd67..f7d5fd7 100644
--- a/modules/rag-answer-service/requirements.txt
+++ b/modules/rag-answer-service/requirements.txt
@@ -1,6 +1,8 @@
 fastapi>=0.137.1
 httpx>=0.28.1
 openai>=2.14.0
+opentelemetry-distro
+opentelemetry-exporter-otlp
 pydantic-settings>=2.12.0
 python-dotenv>=1.2.1
 uvicorn[standard]>=0.38.0
~~~

## Validation performed

| Validation | Result |
| --- | --- |
| Both required OpenTelemetry dependency names are present in requirements.txt | Passed |
| Bootstrap command follows pip install -r requirements.txt in the Dockerfile | Passed |
| Existing Python base image and dependency installation path are preserved | Passed |
| Existing direct Uvicorn CMD is still present | Passed |
| No opentelemetry-instrument CMD was added prematurely | Passed |
| Git whitespace check | Passed; Git only reported normal LF-to-CRLF normalization on this Windows checkout. |

## Test-run details

No unit tests, Docker builds, container runs, image rebuilds, deployments, or trace requests were run. This is intentional: Step 04 explicitly defers the build to Step 05 and the startup command to Step 06.

## Warnings and expected limitations

1. The live Answer pod from Step 03 still uses the old image, so it does not contain these newly declared packages yet.
2. The image build will dynamically install the compatible instrumentation packages found by opentelemetry-bootstrap. Step 05 must prove that opentelemetry-instrument exists in the resulting image.
3. No spans will be exported until Step 06 changes the effective runtime startup command and Step 07 deploys the new image.

## Next decision gate

Step 04 is complete. Approve Step 05 to build the Answer image only and verify the installed OpenTelemetry executable; do not deploy it yet.
