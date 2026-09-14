# Safe CI/CD Image Cleanup

Each Jenkins run creates a new tagged Docker image for every service. The tags
include the Jenkins build number and the Git short SHA, so they accumulate even
after a newer deployment is healthy.

This POC has three distinct places where image/history data can accumulate:

1. The Docker host image store used while Jenkins builds the images.
2. The Docker Desktop Kubernetes node's containerd image store after Jenkins
   imports the images.
3. Kubernetes Deployment rollout history, represented by old ReplicaSets.

## Retention policy

- Docker host tags: keep the newest four tagged CI images per service. This is
  the deployed version plus three previous versions under normal Jenkins flow.
- Kubernetes rollout history: every application Deployment has a
  revisionHistoryLimit of 3.
- The cleanup script always protects an image currently referenced by a
  Deployment in the rag-poc namespace. If that image is unexpectedly older
  than the newest four tags, it is retained in addition to the normal set.

The Jenkins cleanup stage runs only after all deployment, rollout, and complete
stack verification stages have succeeded. A cleanup problem can mark that stage
unstable, but it does not roll back or fail an otherwise healthy deployment.

## Run locally

Preview the result without changing Docker images:

    .\scripts\cleanup-old-cicd-images.ps1

Delete eligible old CI tags after reviewing the preview:

    .\scripts\cleanup-old-cicd-images.ps1 -Keep 4 -Execute

The script only considers the five application repositories and tags in the
Jenkins build-number/git-short-SHA format. It ignores dangling/untagged images
and all non-CI tags. If kubectl is unavailable, a Deployment cannot be found,
or the deployed image cannot be matched safely, that service is skipped instead
of risking deletion.

## Build cache and containerd

After image retention, Jenkins tries to remove Docker builder cache older than
24 hours with docker builder prune -f --filter "until=24h". If the installed
Docker CLI does not support that filter, it falls back to the safe supported
command docker builder prune -f. Neither command removes tagged runtime images.

Jenkins first builds images in the Docker host store and then imports them into
the Docker Desktop Kubernetes node/containerd. Host Docker retention and
Kubernetes ReplicaSet history are explicitly managed here. Old unused
containerd images/layers are deliberately left to Kubernetes and container
runtime garbage collection for this local POC. Consider manual containerd
cleanup only if measured disk growth becomes a real issue.

docker system prune -a and docker image prune -a are intentionally not used:
they can remove broad sets of locally useful images outside this CI retention
policy.

## Jenkins compatibility

The Jenkins agent needs PowerShell (pwsh preferred) available on its PATH for
the retention script to run. If it is absent, the cleanup stage is marked
unstable with a warning while the successful deployment remains successful.
