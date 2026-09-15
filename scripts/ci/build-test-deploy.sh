#!/usr/bin/env bash
set -euo pipefail

service_csv="${1:?service list is required}"
image_tag="${2:?image tag is required}"
namespace="${3:?namespace is required}"
kubeconfig="${4:?kubeconfig is required}"
kind_node="${5:?Kubernetes node container is required}"

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
  local service="$1"
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
  local result_dir="test-results/$1"
  mkdir -p "$result_dir"
  current_test_container="${repository}-tests-${BUILD_NUMBER:-local}"
  docker rm -f "$current_test_container" >/dev/null 2>&1 || true

  set +e
  docker run --name "$current_test_container" "${test_env[@]}" "$current_test_image"
  local test_rc=$?
  set -e

  docker cp "$current_test_container:/tmp/test-results/pytest.xml" \
    "$result_dir/pytest.xml" >/dev/null 2>&1 || true
  docker rm -f "$current_test_container" >/dev/null 2>&1 || true
  current_test_container=""
  return "$test_rc"
}

deploy_service() {
  local runtime_image="${repository}:${image_tag}"
  current_test_image="${repository}:test-${image_tag}"

  echo "============================================================"
  echo "BUILD/TEST: $repository"
  echo "============================================================"
  docker build --target test -t "$current_test_image" -f "$dockerfile" "$context"
  if [[ "$test_mode" == "container" ]]; then
    run_container_tests "$repository"
  fi
  docker image rm "$current_test_image" >/dev/null 2>&1 || true
  current_test_image=""

  echo "============================================================"
  echo "BUILD/DEPLOY: $runtime_image"
  echo "============================================================"
  docker build --target runtime -t "$runtime_image" -f "$dockerfile" "$context"
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

IFS=',' read -r -a selected_services <<<"$service_csv"
for service in "${selected_services[@]}"; do
  configure_service "$service"
  deploy_service
done
