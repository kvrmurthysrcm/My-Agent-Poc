$ErrorActionPreference = "Stop"

$OutputFile = "D:\common\documentation\docker\jenkins\kubeconfig-jenkins"

$clusterName = kubectl config view --minify -o jsonpath='{.contexts[0].context.cluster}'
$server = kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'

if (-not $clusterName) { throw "Unable to determine the current Kubernetes cluster name." }
if (-not $server) { throw "Unable to determine the current Kubernetes API server." }

$containerServer = $server `
    -replace 'https://127\.0\.0\.1:', 'https://host.docker.internal:' `
    -replace 'https://localhost:', 'https://host.docker.internal:'

kubectl config view --raw --minify --flatten | Set-Content -Encoding ascii $OutputFile

kubectl --kubeconfig=$OutputFile config set-cluster $clusterName `
    --server=$containerServer `
    --insecure-skip-tls-verify=true | Out-Null

kubectl --kubeconfig=$OutputFile config unset "clusters.$clusterName.certificate-authority" 2>$null | Out-Null
kubectl --kubeconfig=$OutputFile config unset "clusters.$clusterName.certificate-authority-data" 2>$null | Out-Null

Write-Host "Created Jenkins kubeconfig: $OutputFile"
Write-Host "Cluster: $clusterName"
Write-Host "Container-visible API server: $containerServer"
