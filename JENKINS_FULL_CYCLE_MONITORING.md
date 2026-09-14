# Jenkins Full-Cycle Monitoring and Validation

This guide starts **after `git push`**. The goal is to prove that GitHub is the source of the change, Jenkins detects and builds it, Docker images are produced, Kubernetes deploys them, and the running stack corresponds to the pushed Git commit.

## 1. Do not click Build Now

If the Jenkins job is configured with Poll SCM, leave Jenkins alone after the push. The automatic trigger is part of the test.

Recommended local POC polling schedule:

```text
H/2 * * * *
```

This checks SCM approximately every two minutes and starts a build only when Jenkins detects a new commit.

## 2. Confirm the pushed Git commit

From the project directory:

```powershell
git log -1 --oneline
git rev-parse --short HEAD
```

Keep the short SHA. Jenkins image tags use the build number and Git SHA.

## 3. Watch Jenkins

Open the Jenkins job page and wait for a new build to appear automatically.

Open the new build and use **Console Output** (or Stage View/Pipeline view if installed). Confirm these phases progress in order:

1. Checkout
2. Verify Jenkins Tooling
3. Apply Common Kubernetes Resources
4. RAG Ingest: test/build/load/deploy/verify
5. RAG Search: test/build/load/deploy/verify
6. RAG Answer: test/build/load/deploy/verify
7. Online Library: test/build/load/deploy/verify
8. Secure API: test/build/load/deploy/verify
9. Verify Complete RAG Stack

The pytest stages are currently intentionally non-blocking and may mark a stage unstable while allowing the first full-cycle CI/CD validation to continue.

## 4. Watch Kubernetes while Jenkins runs

In a second PowerShell window:

```powershell
kubectl -n rag-poc get pods -w
```

Expected behavior during deployments:

- a new ReplicaSet/pod is created,
- the new pod moves through `Pending` / `ContainerCreating` / `Running`,
- readiness becomes `1/1`,
- the old pod terminates after the new pod is ready.

In another window, optional:

```powershell
kubectl -n rag-poc get deployments -w
```

## 5. Check rollout state if a stage pauses or fails

```powershell
kubectl -n rag-poc get all
kubectl -n rag-poc get pods -o wide
kubectl -n rag-poc get events --sort-by=.lastTimestamp
```

For one service:

```powershell
kubectl -n rag-poc describe deployment rag-search-service
kubectl -n rag-poc logs deployment/rag-search-service --tail=200
```

Replace the deployment name with:

- `rag-ingest-service`
- `rag-search-service`
- `rag-answer-service`
- `online-library`
- `secure-api`

## 6. Confirm the deployed image tags

After Jenkins succeeds:

```powershell
kubectl -n rag-poc get deployment rag-ingest-service -o jsonpath="{.spec.template.spec.containers[0].image}"; echo
kubectl -n rag-poc get deployment rag-search-service -o jsonpath="{.spec.template.spec.containers[0].image}"; echo
kubectl -n rag-poc get deployment rag-answer-service -o jsonpath="{.spec.template.spec.containers[0].image}"; echo
kubectl -n rag-poc get deployment online-library -o jsonpath="{.spec.template.spec.containers[0].image}"; echo
kubectl -n rag-poc get deployment secure-api -o jsonpath="{.spec.template.spec.containers[0].image}"; echo
```

Expected form:

```text
rag-search-service:<jenkins-build-number>-<git-short-sha>
```

Compare the SHA suffix with:

```powershell
git rev-parse --short HEAD
```

Matching SHAs prove the running deployment came from the pushed commit.

## 7. Confirm all five deployments are healthy

```powershell
kubectl -n rag-poc get deployments
kubectl -n rag-poc get pods
kubectl -n rag-poc get services
```

All five application deployments should show their desired replicas available and their pods should be `Running`/Ready.

## 8. Start local port-forwards

```powershell
.\scripts\start-port-forwards.bat
```

Then validate health endpoints. The pipeline itself verifies health inside the pods, but these checks prove host-to-cluster access as well.

```powershell
curl.exe http://localhost:8000/health
curl.exe http://localhost:8001/health
curl.exe http://localhost:8002/health
curl.exe http://localhost:8003/health/db
curl.exe http://localhost:8010/health
```

## 9. Perform the business-level full-cycle test through Secure API

Use Secure API as the primary entry point instead of treating the individual services as isolated tests:

1. obtain a Keycloak token,
2. call Secure API with `Authorization: Bearer <token>`,
3. ingest/upload a document through the gateway,
4. wait for ingestion completion,
5. search through the gateway,
6. ask a RAG question through the gateway,
7. verify the answer and returned sources/chunks,
8. exercise Online Library through the Secure API route used by the POC.

This validates the real chain: authentication -> gateway -> downstream service -> PostgreSQL/pgvector/Ollama -> response.

## 10. Useful live diagnostics

Follow logs for one deployment:

```powershell
kubectl -n rag-poc logs -f deployment/secure-api
```

Open another terminal for another service if needed:

```powershell
kubectl -n rag-poc logs -f deployment/rag-answer-service
```

Check recent cluster events:

```powershell
kubectl -n rag-poc get events --sort-by=.lastTimestamp
```

## Optional: clean old CI/CD images

Do this **after** a successful deployment, not before the first validation run.

Preview only (default):

```powershell
.\scripts\cleanup-old-cicd-images.ps1
```

Preview while retaining at least the two newest Docker images per service:

```powershell
.\scripts\cleanup-old-cicd-images.ps1 -Keep 2
```

Actually remove the images shown by the preview:

```powershell
.\scripts\cleanup-old-cicd-images.ps1 -Keep 2 -Execute
```

The script protects images currently referenced by the five Kubernetes deployments. The Kubernetes/containerd portion is deliberately conservative and only runs deletions when `-Execute` is supplied.

For generic Docker build cache cleanup, independently and optionally:

```powershell
docker builder prune
```

Avoid `docker system prune -a` for this POC unless you have deliberately reviewed what Docker considers unused, because it can remove downloaded development images that are intentionally retained.
