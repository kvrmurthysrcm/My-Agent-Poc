#!/usr/bin/env bash
set -euo pipefail

action="${1:?action is required}"
image_tag="${2:?image tag is required}"
namespace="${3:?namespace is required}"
kubeconfig="${4:?kubeconfig is required}"
kind_node="${5:?Kubernetes node container is required}"
service="${6:?service id is required}"

exec > >(sed -u "s/^/[$action][$service] /") 2>&1

current_test_image=""
current_test_container=""

cleanup_test_artifacts() {
  if [[ -n "$current_test_container" ]]; then
    docker rm -f "$current_test_container" >/dev/null 2>&1 || true
  fi
  if [[ -n "$current_test_image" ]]; then
    docker image rm "$current_test_image" >/dev/null 2>&1 || true
  fi
}
trap cleanup_test_artifacts EXIT

configure_service() {
  test_mode="build"
  test_env=()
  case "$service" in
    ingest)
      repository="rag-ingest-service"
      dockerfile="modules/rag-ingest-service/Dockerfile"
      context="modules/rag-ingest-service"
      manifests="k8s/rag-ingest-service"
      deployment="rag-ingest-service"
      timeout="240s"
      test_mode="container"
      test_env=(--add-host=host.docker.internal:host-gateway -e RAG_INGEST_TEST_DATABASE_URL=postgresql://library_user:library_pass@host.docker.internal:5432/online_library_test)
      ;;
    search)
      repository="rag-search-service"
      dockerfile="modules/rag-search-service/Dockerfile"
      context="modules/rag-search-service"
      manifests="k8s/rag-search-service"
      deployment="rag-search-service"
      timeout="180s"
      test_mode="container"
      test_env=(--add-host=host.docker.internal:host-gateway -e RAG_SEARCH_TEST_DATABASE_URL=postgresql://library_user:library_pass@host.docker.internal:5432/online_library_test)
      ;;
    answer)
      repository="rag-answer-service"
      dockerfile="modules/rag-answer-service/Dockerfile"
      context="modules/rag-answer-service"
      manifests="k8s/rag-answer-service"
      deployment="rag-answer-service"
      timeout="180s"
      test_mode="container"
      ;;
    library)
      repository="online-library"
      dockerfile="modules/online_library/Dockerfile"
      context="modules/online_library"
      manifests="k8s/online-library"
      deployment="online-library"
      timeout="240s"
      test_mode="container"
      ;;
    mcp)
      repository="online-library-mcp"
      dockerfile="modules/online_library_mcp/Dockerfile"
      context="."
      manifests="k8s/online-library-mcp"
      deployment="online-library-mcp"
      timeout="180s"
      ;;
    library-agent)
      repository="online-library-agent"
      dockerfile="modules/online_library_agent/Dockerfile"
      context="."
      manifests="k8s/online-library-agent"
      deployment="online-library-agent"
      timeout="240s"
      ;;
    weather)
      repository="weather-agent"
      dockerfile="modules/weather_agent/Dockerfile"
      context="."
      manifests="k8s/weather-agent"
      deployment="weather-agent"
      timeout="180s"
      ;;
    weather-ai)
      repository="weather-ai-agent"
      dockerfile="modules/weather_ai_agent/Dockerfile"
      context="."
      manifests="k8s/weather-ai-agent"
      deployment="weather-ai-agent"
      timeout="300s"
      ;;
    secure)
      repository="secure-api"
      dockerfile="modules/secure_api/Dockerfile"
      context="modules/secure_api"
      manifests="k8s/secure-api"
      deployment="secure-api"
      timeout="180s"
      test_mode="container"
      ;;
    angular)
      repository="angular-ui"
      dockerfile="modules/angular-ui/Dockerfile"
      context="."
      manifests="k8s/angular-ui"
      deployment="angular-ui"
      timeout="180s"
      ;;
    *) echo "Unknown service id: $service" >&2; exit 2 ;;
  esac
}

run_container_tests() {
  local result_dir="test-results/$repository"
  local test_rc
  mkdir -p "$result_dir"
  current_test_container="${repository}-tests-${BUILD_NUMBER:-local}"
  docker rm -f "$current_test_container" >/dev/null 2>&1 || true

  set +e
  if [[ "$service" == "ingest" || "$service" == "search" ]]; then
    # Both suites drop and recreate tables in online_library_test. Serialize
    # only their container test step while other workers continue building.
    db_lock="${WORKSPACE:-/tmp}/my-agent-poc-db-tests.lock"
    mkdir -p "$(dirname "$db_lock")"
    (
      flock 9
      docker run --name "$current_test_container" "${test_env[@]}" "$current_test_image"
    ) 9>"$db_lock"
    test_rc=$?
  else
    docker run --name "$current_test_container" "${test_env[@]}" "$current_test_image"
    test_rc=$?
  fi
  set -e

  docker cp "$current_test_container:/tmp/test-results/pytest.xml" \
    "$result_dir/pytest.xml" >/dev/null 2>&1 || true
  docker rm -f "$current_test_container" >/dev/null 2>&1 || true
  current_test_container=""
  return "$test_rc"
}

build_and_test() {
  local runtime_image="${repository}:${image_tag}"
  current_test_image="${repository}:test-${image_tag}"
  echo "BUILD/TEST: $repository"
  docker build --target test -t "$current_test_image" -f "$dockerfile" "$context"
  if [[ "$test_mode" == "container" ]]; then
    run_container_tests || return $?
  fi
  docker image rm "$current_test_image" >/dev/null 2>&1 || true
  current_test_image=""

  echo "BUILD/RUNTIME: $runtime_image"
  docker build --target runtime -t "$runtime_image" -f "$dockerfile" "$context"

  local size_bytes
  local size_mib
  size_bytes="$(docker image inspect --format '{{.Size}}' "$runtime_image")"
  if ! [[ "$size_bytes" =~ ^[0-9]+$ ]]; then
    echo "Docker returned an invalid image size for $runtime_image: $size_bytes" >&2
    return 1
  fi
  size_mib="$(awk -v bytes="$size_bytes" 'BEGIN { printf "%.2f", bytes / 1048576 }')"
  echo "IMAGE/SIZE: $runtime_image = $size_mib MiB ($size_bytes bytes)"

  if [[ -n "${CI_IMAGE_SIZE_DIR:-}" ]]; then
    mkdir -p "$CI_IMAGE_SIZE_DIR"
    printf '%s\t%s\t%s\t%s\n' \
      "$service" "$runtime_image" "$size_bytes" "$size_mib" \
      >"$CI_IMAGE_SIZE_DIR/$service.tsv"
  fi
}

deploy() {
  local runtime_image="${repository}:${image_tag}"
  echo "DEPLOY: $runtime_image"
  docker image inspect "$runtime_image" >/dev/null
  docker save "$runtime_image" | docker exec -i "$kind_node" ctr -n k8s.io images import -

  [[ ! -f "$manifests/configmap.yaml" ]] || kubectl --kubeconfig "$kubeconfig" apply -f "$manifests/configmap.yaml"
  [[ ! -f "$manifests/secret.yaml" ]] || kubectl --kubeconfig "$kubeconfig" apply -f "$manifests/secret.yaml"
  kubectl --kubeconfig "$kubeconfig" apply -f "$manifests/service.yaml"
  sed "s|__IMAGE__|$runtime_image|g" "$manifests/deployment.yaml" |
    kubectl --kubeconfig "$kubeconfig" apply -f -
  kubectl --kubeconfig "$kubeconfig" -n "$namespace" rollout status \
    "deployment/$deployment" --timeout="$timeout"
  kubectl --kubeconfig "$kubeconfig" -n "$namespace" get pods \
    -l "app=$deployment" -o wide
}

configure_service
case "$action" in
  build-test) build_and_test ;;
  deploy) deploy ;;
  *) echo "Unknown worker action: $action" >&2; exit 2 ;;
esac
