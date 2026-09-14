# RAG Answer Service - Local Jenkins/Docker/Kubernetes Pipeline

This pipeline is tailored to the existing `modules/rag-answer-service` module.

## Why this service first

The repository is a multi-service POC, not one deployable application. `rag-answer-service` is a good first CI/CD target because it already has:

- FastAPI app: `app.main:app`
- Port: `8002`
- Requirements: `modules/rag-answer-service/requirements.txt`
- Tests: `modules/rag-answer-service/tests`
- Health endpoint: `/health`
- Readiness endpoint: `/ready`

## Files added

- `Jenkinsfile`
- `modules/rag-answer-service/Dockerfile`
- `modules/rag-answer-service/.dockerignore`
- `k8s/rag-answer-service/namespace.yaml`
- `k8s/rag-answer-service/configmap.yaml`
- `k8s/rag-answer-service/deployment.yaml`
- `k8s/rag-answer-service/service.yaml`
- `scripts/prepare-jenkins-kubeconfig.ps1`

A matching Jenkins-host `docker-compose.yml` is included separately in the bundle.

## One-time Kubernetes access setup

From PowerShell on Windows, run:

```powershell
cd D:\common\documentation\docker\jenkins
powershell -ExecutionPolicy Bypass -File <path-to-project>\scripts\prepare-jenkins-kubeconfig.ps1
```

It creates:

```text
D:\common\documentation\docker\jenkins\kubeconfig-jenkins
```

The supplied Jenkins Compose file mounts that as:

```text
/var/jenkins_home/.kube/config
```

Then recreate Jenkins:

```powershell
docker compose down
docker compose up -d
```

Test from Jenkins:

```powershell
docker exec jenkins kubectl get nodes
```

That command must work before enabling the deploy stage.

## Jenkins job

Recommended job type for the first run: `Pipeline`.

Configure Pipeline -> Definition:

```text
Pipeline script from SCM
```

SCM:

```text
Git
```

Repository:

```text
https://github.com/kvrmurthysrcm/My-Agent-Poc.git
```

Branch for the current repository:

```text
*/master
```

Script Path:

```text
Jenkinsfile
```

## What the pipeline does

1. Checks out the repository.
2. Calculates immutable image tag `<BUILD_NUMBER>-<short SHA>`.
3. Builds the Docker `test` stage using Python 3.13.
4. Runs pytest inside a temporary container.
5. Copies `pytest.xml` out of the container and publishes it in Jenkins.
6. Builds the production image.
7. Verifies Kubernetes access.
8. Loads the exact image into Docker Desktop's `desktop-control-plane` kind node.
9. Applies namespace/config/service/deployment YAML.
10. Waits for Kubernetes rollout to finish.

Example image:

```text
rag-answer-service:12-a7c4e21
```

No Docker Hub is required for this local pipeline.

## Why `imagePullPolicy: Never`

The pipeline imports the image directly into the local Docker Desktop kind node. Kubernetes therefore uses that local image and does not try Docker Hub.

## Runtime dependencies

The existing service expects RAG Search and Ollama. The ConfigMap currently points to the Windows host through:

```text
RAG_SEARCH_BASE_URL=http://host.docker.internal:8001
OLLAMA_BASE_URL=http://host.docker.internal:11434
```

So for a fully functional `/ready` and answer request, these should be running on the host:

- RAG Search Service on port 8001
- Ollama on port 11434
- model `mistral:latest`

The Kubernetes probes intentionally use `/health` for this first deployment. That validates the deployed process without making the first CI/CD rollout depend on Search/Ollama availability. When those dependencies are also deployed, change readiness to `/ready`.

## Verify after deployment

```powershell
kubectl -n rag-poc get pods
kubectl -n rag-poc get svc
kubectl -n rag-poc logs deployment/rag-answer-service
```

To open the service locally:

```powershell
kubectl -n rag-poc port-forward svc/rag-answer-service 8002:8002
```

Then browse:

```text
http://localhost:8002/ui/answer
http://localhost:8002/health
http://localhost:8002/ready
```

## Important next step

Do not containerize all services at once. First get this module green end-to-end. Then reuse this pattern for:

1. `rag-search-service`
2. `rag-ingest-service`
3. `secure_api`
4. remaining services

At that point we can replace `host.docker.internal` dependencies with Kubernetes Service DNS names such as `http://rag-search-service:8001`.
