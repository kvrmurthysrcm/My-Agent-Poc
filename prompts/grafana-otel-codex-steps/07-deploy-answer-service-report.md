# Step 07 - Deploy Instrumented Answer Service Report

**Status:** Completed successfully  
**Run date:** 2026-10-05  
**Scope:** Rebuilt and deployed only `rag-answer-service`, then validated its Kubernetes rollout and OpenTelemetry launch configuration.

## Deployment result

The fresh local runtime image was built successfully with the instrumented Docker CMD:

~~~text
docker build --target runtime -t rag-answer-service:local -f modules\rag-answer-service\Dockerfile modules\rag-answer-service
~~~

| Item | Result |
| --- | --- |
| Image tag deployed | `rag-answer-service:local` |
| Local image ID | `sha256:c1c7c66dfa5afb53f7f4a86134db047e482c176da169f1f7d3ab5021a190b798` |
| Image size | 74,177,763 bytes |
| Namespace | `rag-poc` |
| Deployment | `rag-answer-service` |
| New pod | `rag-answer-service-b9dc7659f-mpxxm` |
| Pod IP | `10.1.0.17` |
| Ready state | `True` (`1/1` ready) |
| Restarts | `0` |
| Rollout result | `deployment "rag-answer-service" successfully rolled out` |

Only the Answer Service ConfigMap, Service, and Deployment were applied. The ConfigMap and Service were unchanged; the Deployment was configured to use the newly built local image. No other service was rebuilt or deployed.

## Image and process command validation

The rebuilt image configuration contains the required launch command:

~~~text
opentelemetry-instrument python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
~~~

The live Kubernetes Deployment has no `command` or `args` override, so Kubernetes uses that image CMD as its effective startup configuration.

Inside the Ready pod:

~~~text
/usr/local/bin/opentelemetry-instrument
opentelemetry-instrument 0.66b0
~~~

`/proc/1/cmdline` reports the final exec'd application process as:

~~~text
/usr/local/bin/python -m uvicorn app.main:app --host 0.0.0.0 --port 8002
~~~

This is expected for `opentelemetry-instrument`: the launcher configures auto-instrumentation and then execs the target process. PID 1 therefore becomes Python rather than retaining the wrapper name. The PID 1 environment confirms that the launcher added the automatic-instrumentation path:

~~~text
PYTHONPATH=/usr/local/lib/python3.13/site-packages/opentelemetry/instrumentation/auto_instrumentation:/app
~~~

Thus, the image/Deployment launch command contains `opentelemetry-instrument`, the executable exists in the pod, and the running process retains its auto-instrumentation configuration.

## OTEL environment validation

All previously configured OpenTelemetry Deployment variables remain present in the new pod:

| Variable | Effective value |
| --- | --- |
| `OTEL_SERVICE_NAME` | `rag-answer-service` |
| `OTEL_RESOURCE_ATTRIBUTES` | `service.namespace=rag-poc,deployment.environment=local` |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | `http://host.docker.internal:4318` |
| `OTEL_EXPORTER_OTLP_PROTOCOL` | `http/protobuf` |
| `OTEL_TRACES_EXPORTER` | `otlp` |
| `OTEL_METRICS_EXPORTER` | `otlp` |
| `OTEL_LOGS_EXPORTER` | `otlp` |
| `OTEL_PYTHON_LOG_CORRELATION` | `true` |

## Startup logs

The most recent 200 pod-log lines showed a normal service startup:

~~~text
INFO: Started server process [1]
INFO: Waiting for application startup.
INFO httpx ... GET http://host.docker.internal:11434/api/tags "HTTP/1.1 200 OK"
INFO app.main ... Ollama answer startup check passed...
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8002
~~~

Subsequent health probes returned HTTP 200. No obvious OpenTelemetry exporter errors or application startup errors appeared in the retrieved logs.

## Validation and test-run details

| Validation | Result |
| --- | --- |
| Fresh runtime image build | Passed |
| Deployment references `rag-answer-service:local` | Passed |
| Running image ID matches fresh local image | Passed |
| Kubernetes rollout | Passed |
| New pod Ready with no restarts | Passed |
| All eight `OTEL_*` variables retained | Passed |
| `opentelemetry-instrument` executable/version in pod | Passed |
| Image CMD and no Kubernetes override | Passed |
| PID 1 auto-instrumentation `PYTHONPATH` | Passed |
| Pod startup/error-log review | Passed; no obvious errors |

The `python:3.13-slim` runtime image does not include `ps`, so PID 1 was inspected safely through `/proc/1/cmdline` and `/proc/1/environ` instead. This was a validation-method limitation only, not a deployment issue.

No unit-test suite, application trace request, collector connectivity request, or Tempo query was run in this deployment step. Those are intentionally deferred to the subsequent verification steps. In particular, a successful rollout and auto-instrumentation setup do not by themselves prove that the pod can reach the host collector or that Tempo has received a trace.

## Next decision gate

Step 07 is complete. Approve Step 08 to verify pod-to-LGTM/OTLP connectivity; no subsequent step has been started.
