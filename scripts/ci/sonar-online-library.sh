#!/usr/bin/env bash
set -uo pipefail

module_name="online-library"
module_path="${WORKSPACE:?WORKSPACE is required}/modules/online_library"
report_dir="${WORKSPACE}/build-reports/sonar"
summary_file="$report_dir/online-library-summary.txt"
scanner_log="$report_dir/online-library-scanner.log"

sonar_host_url="${SONAR_HOST_URL:-http://sonarqube:9000}"
sonar_network="${SONAR_DOCKER_NETWORK:-keycloak_keycloak-network}"
sonar_project_key="${SONAR_PROJECT_KEY:-my-agent-poc-online-library}"
scanner_image="${SONAR_SCANNER_IMAGE:-sonarsource/sonar-scanner-cli:12.1.0.3233_8.0.1}"
project_version="${BUILD_NUMBER:-local}-${GIT_SHORT:-unknown}"
dashboard_url="${sonar_host_url%/}/dashboard?id=${sonar_project_key}"
scanner_container="sonar-online-library-${BUILD_NUMBER:-local}-$$"
scanner_work_volume="${scanner_container}-work"

mkdir -p "$report_dir"
: >"$scanner_log"

cleanup_scanner() {
  docker rm -f "$scanner_container" >/dev/null 2>&1 || true
  docker volume rm "$scanner_work_volume" >/dev/null 2>&1 || true
}
trap cleanup_scanner EXIT

write_summary() {
  local status="$1"
  local recommendation="$2"
  cat >"$summary_file" <<EOF
module=$module_name
project_key=$sonar_project_key
project_version=$project_version
server=$sonar_host_url
dashboard=$dashboard_url
scanner_image=$scanner_image
status=$status
recommendation=$recommendation
EOF
}

fail_advisory() {
  local message="$1"
  echo "SONAR/ADVISORY: $message" | tee -a "$scanner_log"
  write_summary "ATTENTION_REQUIRED" "$message"
  exit 1
}

[[ -d "$module_path" ]] || fail_advisory "Online Library source directory was not found."
[[ -n "${SONAR_TOKEN:-}" ]] || fail_advisory "Create a Jenkins Secret text credential and configure SONAR_TOKEN_CREDENTIALS_ID."
docker network inspect "$sonar_network" >/dev/null 2>&1 || \
  fail_advisory "Docker network '$sonar_network' is unavailable; SonarQube and the scanner must share a network."

echo "SONAR/START: module=$module_name project=$sonar_project_key server=$sonar_host_url"
echo "SONAR/MODE: advisory (scanner or Quality Gate failure will not block deployment)"

set +e
docker volume create "$scanner_work_volume" >/dev/null
docker create --name "$scanner_container" \
  --network "$sonar_network" \
  --user 0:0 \
  --cap-drop ALL \
  --security-opt no-new-privileges:true \
  --workdir /usr/src/modules/online_library \
  --volume "$scanner_work_volume:/usr/src" \
  --volume sonar-scanner-cache:/opt/sonar-scanner/.sonar/cache \
  -e SONAR_HOST_URL="$sonar_host_url" \
  -e SONAR_TOKEN \
  "$scanner_image" \
  -Dsonar.projectKey="$sonar_project_key" \
  -Dsonar.projectVersion="$project_version" >/dev/null
create_rc=$?
if [[ "$create_rc" -eq 0 ]]; then
  docker cp "${WORKSPACE}/." "$scanner_container:/usr/src"
  copy_rc=$?
else
  copy_rc=1
fi
if [[ "$create_rc" -eq 0 && "$copy_rc" -eq 0 ]]; then
  docker start --attach "$scanner_container" 2>&1 | tee "$scanner_log"
  scanner_rc=${PIPESTATUS[0]}
else
  scanner_rc=1
  echo "Unable to create the isolated scanner workspace (create=$create_rc copy=$copy_rc)." | tee "$scanner_log"
fi
set -e

if [[ "$scanner_rc" -eq 0 ]]; then
  write_summary "PASSED" "Analysis completed and the current Sonar Quality Gate passed. Review new issues, security hotspots, duplication, and maintainability findings on the dashboard."
  echo "SONAR/RESULT: PASSED - $dashboard_url"
  exit 0
fi

write_summary "ATTENTION_REQUIRED" "The scan, server connection, background processing, or Quality Gate failed. Review online-library-scanner.log and the Sonar dashboard; deployment continued because this check is advisory."
echo "SONAR/RESULT: ATTENTION_REQUIRED (exit code $scanner_rc) - $dashboard_url"
exit "$scanner_rc"
