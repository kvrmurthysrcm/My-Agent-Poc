# Step 06 - Instrument Answer Startup Report

**Status:** Completed successfully  
**Run date:** 2026-10-05  
**Scope:** Changed only the Answer runtime Docker CMD and created this report. No image was built, no image was deployed, and no Kubernetes resource was changed.

## Startup change

The existing runtime command was:

~~~text
python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
~~~

The new runtime command is:

~~~text
opentelemetry-instrument python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
~~~

The application module path, Python module invocation, host, port, and all Uvicorn options are preserved. OpenTelemetry now wraps the same Uvicorn process rather than replacing its startup behavior.

## Dockerfile diff

~~~diff
diff --git a/modules/rag-answer-service/Dockerfile b/modules/rag-answer-service/Dockerfile
index 59db520..ae8c670 100644
--- a/modules/rag-answer-service/Dockerfile
+++ b/modules/rag-answer-service/Dockerfile
@@ -14,7 +14,8 @@ RUN apt-get update \
 
 COPY requirements.txt ./requirements.txt
 RUN python -m pip install --upgrade pip \
-    && pip install -r requirements.txt
+    && pip install -r requirements.txt \
+    && opentelemetry-bootstrap -a install
 
 FROM base AS test
@@ -27,4 +28,4 @@ CMD ["python", "-m", "pytest", "-q", "--junitxml=/tmp/test-results/pytest.xml",
 FROM base AS runtime
 COPY app ./app
 EXPOSE 8002
-CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
+CMD ["opentelemetry-instrument", "python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8002"]
~~~

The earlier dependency/bootstrap lines are included because they remain uncommitted Step 04 changes in the same Dockerfile. The Step 06-specific change is the final CMD line only.

## Kubernetes override checks

Both source and live Kubernetes configuration were inspected:

| Check | Result |
| --- | --- |
| k8s/rag-answer-service/deployment.yaml command | Not set |
| k8s/rag-answer-service/deployment.yaml args | Not set |
| Live rag-answer-service Deployment command | Not set |
| Live rag-answer-service Deployment args | Not set |

The live Deployment remains in rag-poc and currently references rag-answer-service:46-61072fb. With no command or args override, Kubernetes will use the Docker image CMD after the new image is rebuilt and deployed.

## Effective command after the next approved build/deployment

~~~text
opentelemetry-instrument python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
~~~

This will activate the packages verified in Step 05, including FastAPI/ASGI and HTTPX automatic instrumentation, while reading the OTEL_* environment variables already configured on the Answer Deployment in Step 03.

## Important image state

The local image built in Step 05 has the old command:

~~~text
["python","-m","uvicorn","app.main:app","--host","0.0.0.0","--port","8002"]
~~~

It was intentionally not rebuilt in this step. Do not deploy rag-answer-service:local from Step 05; it does not contain the Step 06 startup change. A fresh image build is required before deployment.

## Validation performed

| Validation | Result |
| --- | --- |
| Exact instrumented CMD and original Uvicorn arguments in Dockerfile | Passed |
| Source Kubernetes command/args override inspection | Passed; none found |
| Live Kubernetes command/args override inspection | Passed; none found |
| Dockerfile diff whitespace check | Passed; Git only noted normal LF-to-CRLF normalization on this Windows checkout. |
| Image build | Not run, by design |
| Deployment or rollout | Not run, by design |

## Test-run details

No unit tests, Docker builds, container runs, deployments, rollouts, or trace requests were run. Step 06 is a startup-command source change only; build and deployment validation are deferred to the next approved step.

## Next decision gate

Step 06 is complete. Approve Step 07 to rebuild the Answer image with this startup command, deploy only Answer, and verify Kubernetes readiness.
