#!/usr/bin/env bash
set -uo pipefail

service="${1:?service id is required}"
sonar_host_url="${SONAR_HOST_URL:-http://sonarqube:9000}"
sonar_network="${SONAR_DOCKER_NETWORK:-keycloak_keycloak-network}"
scanner_image="${SONAR_SCANNER_IMAGE:-sonarsource/sonar-scanner-cli:12.1.0.3233_8.0.1}"
report_dir="${WORKSPACE:?WORKSPACE is required}/build-reports/sonar"

case "$service" in
  ingest)
    module_name="rag-ingest-service"
    module_relative="modules/rag-ingest-service"
    test_report_name="rag-ingest-service"
    sonar_project_key="my-agent-poc-rag-ingest"
    ;;
  search)
    module_name="rag-search-service"
    module_relative="modules/rag-search-service"
    test_report_name="rag-search-service"
    sonar_project_key="my-agent-poc-rag-search"
    ;;
  answer)
    module_name="rag-answer-service"
    module_relative="modules/rag-answer-service"
    test_report_name="rag-answer-service"
    sonar_project_key="my-agent-poc-rag-answer"
    ;;
  library)
    module_name="online-library"
    module_relative="modules/online_library"
    test_report_name="online-library"
    sonar_project_key="my-agent-poc-online-library"
    ;;
  secure)
    module_name="secure-api"
    module_relative="modules/secure_api"
    test_report_name="secure-api"
    sonar_project_key="my-agent-poc-secure-api"
    ;;
  *)
    echo "Unknown Sonar service id: $service" >&2
    exit 2
    ;;
esac

module_path="$WORKSPACE/$module_relative"
ci_report_dir="$module_path/.ci-reports"
summary_file="$report_dir/$module_name-summary.txt"
scanner_log="$report_dir/$module_name-scanner.log"
build_reference="jenkins-${BUILD_NUMBER:-local}-${GIT_SHORT:-unknown}"
dashboard_url="${sonar_host_url%/}/dashboard?id=${sonar_project_key}"
scanner_container="sonar-${service}-${BUILD_NUMBER:-local}-$$"
scanner_work_volume="${scanner_container}-work"
scanner_home_volume="sonar-scanner-home"
prep_container="${scanner_container}-prep"

mkdir -p "$report_dir"
: >"$scanner_log"

cleanup_scanner() {
  docker rm -f "$prep_container" >/dev/null 2>&1 || true
  docker rm -f "$scanner_container" >/dev/null 2>&1 || true
  docker volume rm "$scanner_work_volume" >/dev/null 2>&1 || true
  rm -rf "$ci_report_dir"
}
trap cleanup_scanner EXIT

write_summary() {
  local status="$1"
  local recommendation="$2"
  cat >"$summary_file" <<EOF
module=$module_name
project_key=$sonar_project_key
build_reference=$build_reference
server=$sonar_host_url
dashboard=$dashboard_url
scanner_image=$scanner_image
status=$status
recommendation=$recommendation
EOF
}

fail_advisory() {
  local message="$1"
  echo "SONAR/ADVISORY[$service]: $message" | tee -a "$scanner_log"
  write_summary "ATTENTION_REQUIRED" "$message"
  exit 1
}

[[ -d "$module_path" ]] || fail_advisory "Source directory was not found: $module_relative"
[[ -n "${SONAR_TOKEN:-}" ]] || fail_advisory "The project analysis token was not supplied."
docker network inspect "$sonar_network" >/dev/null 2>&1 || \
  fail_advisory "Docker network '$sonar_network' is unavailable."

mkdir -p "$ci_report_dir"
for report_name in pytest.xml coverage.xml; do
  source_report="$WORKSPACE/test-results/$test_report_name/$report_name"
  [[ -s "$source_report" ]] || fail_advisory "Required test report is missing: $source_report"
  cp "$source_report" "$ci_report_dir/$report_name"
done

echo "SONAR/START[$service]: module=$module_name project=$sonar_project_key server=$sonar_host_url"
echo "SONAR/MODE[$service]: advisory"

set +e
docker volume create "$scanner_work_volume" >/dev/null
docker volume create "$scanner_home_volume" >/dev/null
docker create --name "$prep_container" \
  --user 0:0 \
  --entrypoint /bin/sh \
  --volume "$scanner_work_volume:/usr/src" \
  --volume "$scanner_home_volume:/opt/sonar-scanner/.sonar" \
  "$scanner_image" -c 'sleep 600' >/dev/null
prep_create_rc=$?
if [[ "$prep_create_rc" -eq 0 ]]; then
  docker start "$prep_container" >/dev/null
  prep_start_rc=$?
else
  prep_start_rc=1
fi
if [[ "$prep_start_rc" -eq 0 ]]; then
  docker cp "$WORKSPACE/." "$prep_container:/usr/src"
  copy_rc=$?
else
  copy_rc=1
fi
if [[ "$copy_rc" -eq 0 ]]; then
  docker exec "$prep_container" /bin/sh -c \
    'mkdir -p /opt/sonar-scanner/.sonar/cache /opt/sonar-scanner/.sonar/_tmp && chown -R 1000:1000 /usr/src /opt/sonar-scanner/.sonar'
  ownership_rc=$?
else
  ownership_rc=1
fi
docker rm -f "$prep_container" >/dev/null 2>&1

if [[ "$ownership_rc" -eq 0 ]]; then
  docker create --name "$scanner_container" \
    --network "$sonar_network" \
    --cap-drop ALL \
    --security-opt no-new-privileges:true \
    --workdir "/usr/src/$module_relative" \
    --volume "$scanner_work_volume:/usr/src" \
    --volume "$scanner_home_volume:/opt/sonar-scanner/.sonar" \
    -e SONAR_HOST_URL="$sonar_host_url" \
    -e SONAR_TOKEN \
    "$scanner_image" \
    -Dsonar.projectKey="$sonar_project_key" \
    -Dsonar.buildString="$build_reference" \
    -Dsonar.analysis.buildNumber="${BUILD_NUMBER:-local}" \
    -Dsonar.analysis.buildUrl="${BUILD_URL:-unavailable}" \
    -Dsonar.scm.revision="${GIT_COMMIT:-unknown}" >/dev/null
  create_rc=$?
else
  create_rc=1
fi
if [[ "$create_rc" -eq 0 ]]; then
  docker start --attach "$scanner_container" 2>&1 | tee "$scanner_log"
  scanner_rc=${PIPESTATUS[0]}
else
  scanner_rc=1
  echo "Unable to prepare scanner workspace (prep=$prep_create_rc start=$prep_start_rc copy=$copy_rc ownership=$ownership_rc create=$create_rc)." | tee "$scanner_log"
fi
set -e

if [[ "$scanner_rc" -eq 0 ]]; then
  recommendation="Analysis completed. Review issues, hotspots, coverage, test execution, duplication, and historical trends."
  write_summary "PASSED" "$recommendation"
  echo "SONAR/RESULT[$service]: PASSED - $dashboard_url"
  exit 0
fi

recommendation="The scan, server connection, background processing, or Quality Gate failed. Deployment continued because this check is advisory."
write_summary "ATTENTION_REQUIRED" "$recommendation"
echo "SONAR/RESULT[$service]: ATTENTION_REQUIRED (exit code $scanner_rc) - $dashboard_url"
exit "$scanner_rc"
