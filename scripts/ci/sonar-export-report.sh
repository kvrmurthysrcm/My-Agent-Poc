#!/usr/bin/env bash
set -euo pipefail

selected_csv="${1:-${CI_SERVICES:-}}"
script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exporter="$script_dir/sonar-export-summary.py"
report_dir="${WORKSPACE:?WORKSPACE is required}/build-reports/sonar"
summary_tsv="$report_dir/sonar-summary.tsv"
sonar_network="${SONAR_DOCKER_NETWORK:-keycloak_keycloak-network}"
statuses=()

is_selected() {
  [[ ",$selected_csv," == *",$1,"* ]]
}

summary_name_for() {
  case "$1" in
    ingest) echo "rag-ingest-service-summary.txt" ;;
    search) echo "rag-search-service-summary.txt" ;;
    answer) echo "rag-answer-service-summary.txt" ;;
    library) echo "online-library-summary.txt" ;;
    secure) echo "secure-api-summary.txt" ;;
  esac
}

for service in ingest search answer library secure; do
  is_selected "$service" || continue
  summary_file="$report_dir/$(summary_name_for "$service")"
  if [[ -s "$summary_file" ]] && grep -q '^status=PASSED$' "$summary_file"; then
    statuses+=("$service=SUCCESS")
  else
    statuses+=("$service=ATTENTION_REQUIRED")
  fi
done

status_csv="$(IFS=,; echo "${statuses[*]}")"
export_tmp="${summary_tsv}.tmp"
docker run --rm -i \
  --network "$sonar_network" \
  -e SONAR_HOST_URL="${SONAR_HOST_URL:-http://sonarqube:9000}" \
  -e SONAR_PUBLIC_URL="${SONAR_PUBLIC_URL:-http://localhost:9000}" \
  -e SONAR_REPORT_TOKEN \
  -e SONAR_SCANNER_STATUSES="$status_csv" \
  -e CI_SERVICES="$selected_csv" \
  -e BUILD_NUMBER="${BUILD_NUMBER:-local}" \
  -e GIT_COMMIT="${GIT_COMMIT:-unknown}" \
  --volume "$WORKSPACE:/workspace:ro" \
  python:3.13-slim python - <"$exporter" >"$export_tmp"
mv "$export_tmp" "$summary_tsv"
echo "SONAR/REPORT: $summary_tsv"
