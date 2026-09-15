#!/usr/bin/env bash
set -u

namespace="${1:-rag-poc}"
kubeconfig="${2:-/var/jenkins_home/kubeconfig-jenkins}"
deployments=(
  rag-ingest-service rag-search-service rag-answer-service online-library
  online-library-mcp online-library-agent weather-agent weather-ai-agent
  secure-api angular-ui
)

kubectl --kubeconfig "$kubeconfig" -n "$namespace" get all || true
for deployment in "${deployments[@]}"; do
  kubectl --kubeconfig "$kubeconfig" -n "$namespace" \
    describe deployment "$deployment" || true
  kubectl --kubeconfig "$kubeconfig" -n "$namespace" \
    logs "deployment/$deployment" --tail=100 || true
done
