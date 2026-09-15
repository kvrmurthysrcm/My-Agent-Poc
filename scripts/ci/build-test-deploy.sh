#!/usr/bin/env bash
set -euo pipefail

service_csv="${1:?service list is required}"
image_tag="${2:?image tag is required}"
namespace="${3:?namespace is required}"
kubeconfig="${4:?kubeconfig is required}"
kind_node="${5:?Kubernetes node container is required}"
max_workers="${MAX_PARALLEL_SERVICES:-2}"

if ! [[ "$max_workers" =~ ^[1-4]$ ]]; then
  echo "MAX_PARALLEL_SERVICES must be an integer from 1 through 4." >&2
  exit 2
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
worker="$script_dir/service-worker.sh"
test -f "$worker" || { echo "Missing CI worker: $worker" >&2; exit 1; }

IFS=',' read -r -a selected_services <<<"$service_csv"
declare -A selected=()
for service in "${selected_services[@]}"; do
  case "$service" in
    ingest|search|answer|library|mcp|library-agent|weather|weather-ai|secure|angular)
      selected["$service"]=1
      ;;
    *)
      echo "Unknown service id: $service" >&2
      exit 2
      ;;
  esac
done

run_parallel() {
  local action="$1"
  shift
  local services=("$@")
  [[ ${#services[@]} -gt 0 ]] || return 0

  echo "============================================================"
  echo "PARALLEL $action: ${services[*]} (maximum workers: $max_workers)"
  echo "============================================================"
  printf '%s\0' "${services[@]}" |
    xargs -0 -r -n1 -P "$max_workers" \
      "$BASH" "$worker" "$action" "$image_tag" "$namespace" \
        "$kubeconfig" "$kind_node"
}

# Build and test everything first. If any worker fails, xargs returns non-zero
# and no service is deployed by this run.
run_parallel build-test "${selected_services[@]}"

# Deploy in dependency-aware waves. Services inside a wave may run together,
# but every rollout in a wave must finish before the next wave starts.
wave1=()
wave2=()
wave3=()
wave4=()
for service in ingest search library weather secure; do
  [[ -n "${selected[$service]:-}" ]] && wave1+=("$service")
done
for service in answer mcp weather-ai; do
  [[ -n "${selected[$service]:-}" ]] && wave2+=("$service")
done
[[ -n "${selected[library-agent]:-}" ]] && wave3+=(library-agent)
[[ -n "${selected[angular]:-}" ]] && wave4+=(angular)

run_parallel deploy "${wave1[@]}"
run_parallel deploy "${wave2[@]}"
run_parallel deploy "${wave3[@]}"
run_parallel deploy "${wave4[@]}"

echo "Parallel build/test and dependency-aware deployment completed."
