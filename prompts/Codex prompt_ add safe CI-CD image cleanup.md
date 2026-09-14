Review the existing Jenkins, Docker, and Kubernetes configuration in this project and implement a safe image/history cleanup policy for the current CI/CD pipeline.

Current context:
- Jenkins builds Docker images for these services:
  - rag-ingest-service
  - rag-search-service
  - rag-answer-service
  - online-library
  - secure-api
- Jenkins tags images using build number + Git short SHA, for example:
  - rag-search-service:12-a83c71d
- Jenkins then loads/imports the images into Docker Desktop Kubernetes and deploys them.
- The pipeline is working successfully today. Do not redesign the working CI/CD flow.
- Cleanup must happen only AFTER a successful deployment and successful health/verification stages.
- Do not use aggressive commands such as:
  - docker system prune -a
  - docker image prune -a
- Do not remove an image currently referenced by a Kubernetes deployment.

Implement the following policy.

1. Kubernetes rollout history
For every Kubernetes Deployment used by the five services, set:

revisionHistoryLimit: 3

This should retain only a small number of old ReplicaSets.

Apply this consistently to:
- rag-ingest-service
- rag-search-service
- rag-answer-service
- online-library
- secure-api

Do not otherwise alter resource requests, ports, probes, environment variables, selectors, service names, or existing working configuration.

2. Docker host image retention
Create or update a reusable PowerShell cleanup script under:

scripts/cleanup-old-cicd-images.ps1

The script should handle these repositories:

$Services = @(
    "rag-ingest-service",
    "rag-search-service",
    "rag-answer-service",
    "online-library",
    "secure-api"
)

Required behavior:
- Default retention: keep the newest 4 tagged CI images per service:
  - current/latest deployed image
  - plus 3 previous versions
- Support a parameter such as:
  -Keep 4
- Dry-run by default.
- Require:
  -Execute
  before actually deleting anything.
- Show clearly:
  KEEP
  WOULD REMOVE
  REMOVED
- Never delete the image currently referenced by the Kubernetes deployment in namespace rag-poc.
- Query the currently deployed image using kubectl.
- Ignore untagged/dangling images unless explicitly handled separately.
- Be resilient if:
  - a service has fewer than 4 images
  - kubectl is unavailable
  - a deployment is missing
  - an image is already absent
- Return a non-zero exit code only for real script failures, not because there was nothing to clean.

3. Jenkins post-success cleanup
Add a Jenkins stage near the end of the existing cumulative pipeline, AFTER:
- all service deployments
- rollout verification
- complete stack health verification

Suggested stage name:

Cleanup Old CI Images

The cleanup stage should:
- run only if the build/deployment has reached the successful cleanup point
- execute the PowerShell cleanup script
- retain 4 images per service
- actually execute cleanup, not dry-run
- not make an otherwise successful deployment fail solely because cleanup encountered a non-critical old-image deletion problem

For example, cleanup failure may mark that cleanup stage unstable or emit a warning, but must not roll back or fail a healthy deployment.

Preserve the existing Jenkinsfile structure and existing working build/test/deploy stages.

4. Docker build cache cleanup
Add conservative build-cache cleanup after successful deployment.

Use a safe command such as:

docker builder prune -f

Do not use:
docker system prune -a
docker image prune -a

If possible, add a sensible age filter rather than removing very recent build cache. For example, prune build cache older than 24 hours if supported by the current Docker CLI.

Prefer something similar to:

docker builder prune -f --filter "until=24h"

If that syntax is incompatible with the installed Docker version, keep the safer supported equivalent and document it.

5. Kubernetes/containerd image store
Do NOT add aggressive manual deletion of images from the Kubernetes/containerd node at this time.

Add a concise comment/documentation explaining:
- Jenkins first builds images in Docker.
- Images are then imported/loaded into the Docker Desktop Kubernetes node/containerd.
- Host Docker cleanup and Kubernetes ReplicaSet cleanup are explicitly managed.
- Old unused containerd layers/images should generally be left to Kubernetes/container runtime garbage collection for this local POC.
- Manual containerd cleanup should only be considered later if disk growth becomes an actual issue.

6. Documentation
Create or update a short CI/CD cleanup document, preferably:

CI_CD_IMAGE_CLEANUP.md

Document:
- why images accumulate
- where images/history exist:
  1. Docker host image store
  2. Kubernetes/containerd node image store
  3. Kubernetes ReplicaSet rollout history
- retention policy:
  - Docker: current + 3 previous = 4 total per service
  - Kubernetes revisionHistoryLimit: 3
- cleanup happens only after successful deployment
- dry-run command:
  .\scripts\cleanup-old-cicd-images.ps1
- explicit execution:
  .\scripts\cleanup-old-cicd-images.ps1 -Keep 4 -Execute
- Docker build-cache cleanup policy
- why docker system prune -a is intentionally not used

7. Validation
After modifications:
- validate all Kubernetes YAML
- verify all five Deployment manifests contain:
  revisionHistoryLimit: 3
- validate the PowerShell script syntax
- inspect the Jenkinsfile to confirm cleanup happens only after deployment/verification
- ensure current CI/CD build/test/deploy behavior is unchanged
- do not modify unrelated Python application logic

Before changing files:
1. inspect the existing Jenkinsfile
2. inspect the existing cleanup script if present
3. inspect all five Kubernetes deployment manifests
4. reuse the project's existing naming/style wherever possible

At the end, provide:
- list of changed files
- concise explanation of each change
- exact dry-run cleanup command
- exact real cleanup command
- any assumptions or compatibility concerns

Do not create a new architecture. Modify the current working pipeline conservatively.