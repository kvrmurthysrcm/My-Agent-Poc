#!/usr/bin/env bash
set -euo pipefail

service_csv="${1:?service list is required}"
image_tag="${2:?image tag is required}"
namespace="${3:?namespace is required}"
kubeconfig="${4:?kubeconfig is required}"
kind_node="${5:?Kubernetes node container is required}"
pipeline_action="${6:-all}"
max_workers="${MAX_PARALLEL_SERVICES:-2}"

if ! [[ "$max_workers" =~ ^[1-4]$ ]]; then
  echo "MAX_PARALLEL_SERVICES must be an integer from 1 through 4." >&2
  exit 2
fi
case "$pipeline_action" in
  build-test|deploy|all) ;;
  *) echo "Pipeline action must be build-test, deploy, or all." >&2; exit 2 ;;
esac

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

if [[ "$pipeline_action" == "build-test" || "$pipeline_action" == "all" ]]; then
  report_root="${WORKSPACE:-$PWD}/build-reports"
  report_parts="$report_root/image-sizes"
  report_summary="$report_root/image-sizes.tsv"
  export CI_IMAGE_SIZE_DIR="$report_parts"
  mkdir -p "$report_parts"
  for service in "${selected_services[@]}"; do
    rm -f "$report_parts/$service.tsv"
  done

  # A failed worker stops this stage. The separate deployment stage will not
  # run, so only images that passed their tests can be deployed.
  run_parallel build-test "${selected_services[@]}"

  total_bytes=0
  {
    printf 'service\timage\tsize_bytes\tsize_mib\n'
    for service in "${selected_services[@]}"; do
      part="$report_parts/$service.tsv"
      if [[ ! -s "$part" ]]; then
        echo "Missing image-size result for service: $service" >&2
        exit 1
      fi
      IFS=$'\t' read -r report_service report_image report_bytes report_mib <"$part"
      if ! [[ "$report_bytes" =~ ^[0-9]+$ ]]; then
        echo "Invalid image-size result for service: $service" >&2
        exit 1
      fi
      total_bytes=$((total_bytes + report_bytes))
      printf '%s\t%s\t%s\t%s\n' \
        "$report_service" "$report_image" "$report_bytes" "$report_mib"
    done
    total_mib="$(awk -v bytes="$total_bytes" 'BEGIN { printf "%.2f", bytes / 1048576 }')"
    printf 'TOTAL\tselected-runtime-images\t%s\t%s\n' "$total_bytes" "$total_mib"
  } >"$report_summary"

  echo "============================================================"
  echo "RUNTIME IMAGE SIZE SUMMARY"
  echo "============================================================"
  awk -F '\t' 'NR == 1 { printf "%-18s %-48s %12s %12s\n", "SERVICE", "IMAGE", "BYTES", "MiB"; next }
    { printf "%-18s %-48s %12s %12s\n", $1, $2, $3, $4 }' "$report_summary"
fi

if [[ "$pipeline_action" == "deploy" || "$pipeline_action" == "all" ]]; then
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
fi

echo "Pipeline action '$pipeline_action' completed for: ${selected_services[*]}"
