#!/usr/bin/env bash
set -euo pipefail

base_commit="${1:-}"
head_commit="${2:-HEAD}"
all_services=(ingest search answer library mcp library-agent weather weather-ai secure angular)

emit_all() {
  local IFS=,
  echo "${all_services[*]}"
}

if [[ -z "$base_commit" ]] || ! git cat-file -e "${base_commit}^{commit}" 2>/dev/null; then
  echo "No usable previous commit; selecting every service." >&2
  emit_all
  exit 0
fi

mapfile -t changed_files < <(git diff --name-only "$base_commit" "$head_commit")
if [[ ${#changed_files[@]} -eq 0 ]]; then
  echo "No changed files detected." >&2
  exit 0
fi

declare -A selected=()
rebuild_all=false
for raw_path in "${changed_files[@]}"; do
  path="${raw_path//\\//}"
  [[ -z "$path" ]] && continue
  echo "Changed: $path" >&2

  case "$path" in
    docs/*) ;;
    modules/rag-ingest-service/*|k8s/rag-ingest-service/*) selected[ingest]=1 ;;
    modules/rag-search-service/*|k8s/rag-search-service/*) selected[search]=1 ;;
    modules/rag-answer-service/*|k8s/rag-answer-service/*) selected[answer]=1 ;;
    modules/online_library/*|k8s/online-library/*) selected[library]=1 ;;
    modules/online_library_mcp/*|k8s/online-library-mcp/*) selected[mcp]=1 ;;
    modules/online_library_agent/*|k8s/online-library-agent/*) selected[library-agent]=1 ;;
    modules/weather_agent/*|k8s/weather-agent/*)
      selected[weather]=1
      selected[weather-ai]=1
      ;;
    modules/weather_ai_agent/*|k8s/weather-ai-agent/*) selected[weather-ai]=1 ;;
    modules/secure_api/*|k8s/secure-api/*) selected[secure]=1 ;;
    modules/angular-ui/*|k8s/angular-ui/*) selected[angular]=1 ;;
    *) rebuild_all=true ;;
  esac
done

if [[ "$rebuild_all" == true ]]; then
  echo "Shared, pipeline, or unknown source changed; selecting every service." >&2
  emit_all
  exit 0
fi

plan=()
for service in "${all_services[@]}"; do
  [[ -n "${selected[$service]:-}" ]] && plan+=("$service")
done

if [[ ${#plan[@]} -gt 0 ]]; then
  IFS=,
  echo "${plan[*]}"
else
  echo "Only documentation changed; no service selected." >&2
fi
