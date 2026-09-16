#!/usr/bin/env bash
set -euo pipefail

selected_csv="${1:-}"
report_dir="${WORKSPACE:-$PWD}/build-reports/sonar"
summary_file="$report_dir/sonar-summary.tsv"
public_url="${SONAR_PUBLIC_URL:-http://localhost:9000}"
build_number="${BUILD_NUMBER:-local}"
git_commit="${GIT_COMMIT:-unknown}"

mkdir -p "$report_dir"

is_selected() {
  [[ ",$selected_csv," == *",$1,"* ]]
}

project_key_for() {
  case "$1" in
    ingest) echo "my-agent-poc-rag-ingest" ;;
    search) echo "my-agent-poc-rag-search" ;;
    answer) echo "my-agent-poc-rag-answer" ;;
    library) echo "my-agent-poc-online-library" ;;
    mcp) echo "my-agent-poc-online-library-mcp" ;;
    library-agent) echo "my-agent-poc-online-library-agent" ;;
    weather) echo "my-agent-poc-weather-agent" ;;
    weather-ai) echo "my-agent-poc-weather-ai-agent" ;;
    secure) echo "my-agent-poc-secure-api" ;;
    angular) echo "my-agent-poc-angular-ui" ;;
  esac
}

header='build_number\tgit_commit\tservice\tproject_key\tselected_for_build\tsonar_enabled\tanalyzed_this_build\tanalysis_status\tmetrics_source\tquality_gate\treliability_rating\tsecurity_rating\tmaintainability_rating\tsecurity_hotspots\tcoverage_percent\tnew_coverage_percent\tduplicated_lines_percent\tnew_duplicated_lines_percent\tlines_of_code\ttests\ttest_failures\ttest_errors\tskipped_tests\ttest_execution_time_ms\tanalysis_date\tanalysis_revision\tbuild_reference\tdashboard_url\thistory_url\trecommendation'
printf '%b\n' "$header" >"$summary_file"

for service in ingest search answer library mcp library-agent weather weather-ai secure angular; do
  project_key="$(project_key_for "$service")"
  selected="false"
  is_selected "$service" && selected="true"
  sonar_enabled="false"
  analysis_status="NOT_CONFIGURED"
  recommendation="Create the SonarQube project and onboard this module in a future release."
  if [[ "$service" == "ingest" || "$service" == "search" || \
        "$service" == "answer" || "$service" == "library" || \
        "$service" == "secure" ]]; then
    sonar_enabled="true"
    if [[ "$selected" == "true" ]]; then
      analysis_status="PENDING"
      recommendation="The selected service analysis has not completed yet."
    else
      analysis_status="NOT_SELECTED"
      recommendation="The module was unchanged, so this build did not analyze it."
    fi
  fi
  dashboard="${public_url%/}/dashboard?id=$project_key"
  history="${public_url%/}/project/activity?id=$project_key"
  row=(
    "$build_number" "$git_commit" "$service" "$project_key" "$selected"
    "$sonar_enabled" "false" "$analysis_status" "" "" "" "" "" "" ""
    "" "" "" "" "" "" "" "" "" "" "" "jenkins-${build_number}"
    "$dashboard" "$history" "$recommendation"
  )
  (IFS=$'\t'; printf '%s\n' "${row[*]}") >>"$summary_file"
done

echo "Initialized Sonar inventory report: $summary_file"
