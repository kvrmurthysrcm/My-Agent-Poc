#!/usr/bin/env bash
set -euo pipefail

keep="${KEEP_CI_IMAGES:-3}"
namespace="${K8S_NAMESPACE:-rag-poc}"
kubeconfig="${KUBECONFIG:-}"
kind_node="${KIND_NODE:-desktop-control-plane}"

if ! [[ "$keep" =~ ^[1-9][0-9]*$ ]]; then
  echo "KEEP_CI_IMAGES must be a positive integer." >&2
  exit 2
fi
command -v docker >/dev/null || { echo "docker is required." >&2; exit 1; }
command -v kubectl >/dev/null || { echo "kubectl is required." >&2; exit 1; }

kubectl_args=()
if [[ -n "$kubeconfig" ]]; then kubectl_args+=(--kubeconfig "$kubeconfig"); fi

services=(
  "rag-ingest-service|rag-ingest-service"
  "rag-search-service|rag-search-service"
  "rag-answer-service|rag-answer-service"
  "online-library|online-library"
  "secure-api|secure-api"
  "online-library-mcp|online-library-mcp"
  "online-library-agent|online-library-agent"
  "weather-agent|weather-agent"
  "weather-ai-agent|weather-ai-agent"
  "angular-ui|angular-ui"
)

node_available=false
if [[ "$(docker inspect -f '{{.State.Running}}' "$kind_node" 2>/dev/null || true)" == "true" ]]; then
  node_available=true
else
  echo "WARNING: Kubernetes node container '$kind_node' is unavailable; containerd cleanup will be skipped." >&2
fi

for item in "${services[@]}"; do
  IFS='|' read -r repository deployment <<<"$item"
  deployed="$(kubectl "${kubectl_args[@]}" -n "$namespace" get deployment "$deployment" -o 'jsonpath={.spec.template.spec.containers[0].image}' 2>/dev/null || true)"
  if [[ -z "$deployed" ]]; then
    echo "WARNING: deployment '$deployment' was not found; skipping '$repository' for safety." >&2
    continue
  fi
  deployed="${deployed#docker.io/library/}"

  mapfile -t images < <(
    docker image ls "$repository" --format '{{.Repository}}|{{.Tag}}' |
      awk -F'|' '$2 ~ /^[0-9]+-[0-9a-fA-F]{7,40}$/ { split($2,p,"-"); print p[1] "|" $1 ":" $2 }' |
      sort -t'|' -k1,1nr -k2,2r
  )

  deployed_found=false
  for row in "${images[@]}"; do
    reference="${row#*|}"
    if [[ "$reference" == "$deployed" ]]; then deployed_found=true; break; fi
  done
  if [[ "$deployed_found" != true && ${#images[@]} -gt 0 ]]; then
    echo "WARNING: deployed image '$deployed' is not a local CI tag; skipping '$repository' for safety." >&2
    continue
  fi

  retained=("$deployed")
  for row in "${images[@]}"; do
    reference="${row#*|}"
    [[ ${#retained[@]} -ge $keep ]] && break
    [[ "$reference" == "$deployed" ]] || retained+=("$reference")
  done

  for row in "${images[@]}"; do
    reference="${row#*|}"
    keep_reference=false
    for protected in "${retained[@]}"; do
      if [[ "$reference" == "$protected" ]]; then keep_reference=true; break; fi
    done
    [[ "$keep_reference" == true ]] && continue

    echo "[$repository] removing old CI image $reference"
    if [[ "$node_available" == true ]]; then
      qualified="docker.io/library/$reference"
      node_refs="$(docker exec "$kind_node" ctr -n k8s.io images ls -q)"
      if grep -Fxq "$qualified" <<<"$node_refs"; then
        docker exec "$kind_node" ctr -n k8s.io images rm "$qualified"
      elif grep -Fxq "$reference" <<<"$node_refs"; then
        docker exec "$kind_node" ctr -n k8s.io images rm "$reference"
      fi
    fi
    docker image rm "$reference"
  done

  # Test targets are never deployed or imported, so no test image needs history.
  mapfile -t test_images < <(
    docker image ls "$repository" --format '{{.Repository}}|{{.Tag}}' |
      awk -F'|' '$2 ~ /^test-[0-9]+-[0-9a-fA-F]{7,40}$/ { print $1 ":" $2 }'
  )
  for reference in "${test_images[@]}"; do
    echo "[$repository] removing ephemeral test image $reference"
    docker image rm "$reference"
  done

  echo "[$repository] retained at most $keep runtime CI image(s), including $deployed."
done

