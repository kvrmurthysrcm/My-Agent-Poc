# Step 08 - Verify Pod to LGTM Connectivity Report

**Status:** Completed successfully  
**Run date:** 2026-10-05  
**Scope:** Performed read-only network validation from the deployed Answer Service pod to the configured LGTM OTLP HTTP endpoint. No Kubernetes, Docker, application, or network configuration was changed.

## Target and pod state

| Item | Value |
| --- | --- |
| Namespace | `rag-poc` |
| Deployment | `rag-answer-service` |
| Tested pod | `rag-answer-service-b9dc7659f-mpxxm` |
| Pod state after checks | `Running`, Ready `true`, `0` restarts |
| Configured endpoint | `http://host.docker.internal:4318` |

The checks used the pod's existing Python standard library (`socket` and `http.client`). No diagnostic package or debug tool was installed.

## Pod-to-LGTM connectivity results

| Check | Result | Evidence |
| --- | --- | --- |
| DNS resolution | Passed | `host.docker.internal` resolved to `192.168.65.254` |
| TCP connection to port 4318 | Passed | `socket.create_connection(..., timeout=5)` completed successfully |
| HTTP endpoint reachability | Passed | `GET http://host.docker.internal:4318/` returned `HTTP 404 Not Found` |

The HTTP 404 is an explicit response from the reachable endpoint, rather than a DNS, connection, or timeout failure. The OTLP HTTP receiver uses signal-specific request paths such as `/v1/traces`; this read-only base-path probe intentionally did not submit an OTLP payload or generate a trace.

## LGTM container and log observations

The local collector container is available and healthy:

~~~text
grafana-lgtm | grafana/otel-lgtm:latest | Up 2 days (healthy)
0.0.0.0:4317-4318->4317-4318/tcp
~~~

The latest 200 `grafana-lgtm` log lines showed normal Tempo/Loki maintenance activity, including Tempo WAL block completion and compaction. They did not show an OTLP receiver, exporter, or rejected-request error associated with the Answer pod connectivity probe.

The same log window did contain recurring internal Tempo scheduler messages:

~~~text
method=/tempopb.BackendScheduler/Next ...
rpc error: code = NotFound desc = no jobs found
error calling scheduler
~~~

These are Tempo backend-scheduler messages, not a DNS, TCP, or HTTP 4318 connection failure from the Answer pod. They were recorded as an environmental observation for later trace verification; no local-only fix is indicated by the Step 08 connectivity evidence.

## Validation and test-run details

~~~text
kubectl exec -n rag-poc deployment/rag-answer-service -- python -c <DNS, TCP, and HTTP probe>
DNS_A=192.168.65.254
TCP_CONNECT=PASS
HTTP_STATUS=404 REASON=Not Found

docker logs --tail 200 grafana-lgtm
docker ps --filter name=^/grafana-lgtm$
kubectl get pods -n rag-poc -l app=rag-answer-service ...
~~~

| Validation | Result |
| --- | --- |
| Existing pod tool usage only | Passed |
| DNS lookup from pod | Passed |
| Port 4318 connection from pod | Passed |
| HTTP response from configured endpoint | Passed |
| `grafana-lgtm` health and port mapping | Passed |
| Collector log review | Completed; internal Tempo scheduler errors documented above |
| Post-check Answer pod readiness | Passed |

No configuration or image changes were necessary. This step proves the pod can reach the Docker Desktop host endpoint. It does not prove an Answer trace has been accepted by Tempo; that is the purpose of the next gated step.

## Next decision gate

Step 08 is complete. Approve Step 09 to generate and verify the first real Answer Service trace in Tempo; no subsequent step has been started.
