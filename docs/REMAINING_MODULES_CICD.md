# CI/CD for the remaining modules

The root `Jenkinsfile` now packages and deploys all ten services in one pipeline.
The newly covered modules are:

| Source module | Image repository | Kubernetes Deployment | Port |
|---|---|---|---:|
| `modules/online_library_mcp` | `online-library-mcp` | `online-library-mcp` | 8004 |
| `modules/online_library_agent` | `online-library-agent` | `online-library-agent` | 8005 |
| `modules/weather_agent` | `weather-agent` | `weather-agent` | 8006 |
| `modules/weather_ai_agent` | `weather-ai-agent` | `weather-ai-agent` | 8007 |
| `modules/angular-ui` | `angular-ui` | `angular-ui` | 8080 |

## Pipeline flow

For each selected module Jenkins:

1. Builds the Docker `test` target. Tests/import checks run during this build and
   stop deployment on failure.
2. Builds the tagged `runtime` target.
3. Imports that image into the Docker Desktop Kubernetes node's containerd.
4. Applies the ConfigMap (where used), Service, and rendered Deployment.
5. Waits for rollout completion and a Ready pod.

The Angular runtime uses Nginx with SPA fallback. Requests below `/api/` are
proxied to the in-cluster `secure-api` Service. The Secure API now calls the
in-cluster Online Library MCP and Agent Services instead of host ports.

## Selective behavior and dependencies

Each new module is independently selectable. A `weather_agent` change also
rebuilds `weather_ai_agent` because that image copies the deterministic weather
module. Root or shared changes rebuild all ten services.

## Retention and cleanup

After successful rollout checks, Jenkins runs
`scripts/cleanup-old-cicd-images.sh`. It protects the deployed tag, retains at
most three runtime CI tags per service across Docker and the Kubernetes node's
containerd image store, removes ephemeral test images, and then prunes unused
builder cache. Kubernetes Deployments use `revisionHistoryLimit: 3`.

Cleanup failure marks only that stage unstable so it cannot undo an otherwise
healthy deployment. A local PowerShell equivalent is available at
`scripts/cleanup-old-cicd-images.ps1` and previews changes unless `-Execute` is
provided.

## Runtime prerequisites

- Docker Desktop Kubernetes node container name: `desktop-control-plane`
- Jenkins kubeconfig: `/var/jenkins_home/kubeconfig-jenkins`
- PostgreSQL and Keycloak remain host dependencies for the existing services.
- Ollama remains a host dependency for the Online Library Agent and the default
  Weather AI Agent configuration.
