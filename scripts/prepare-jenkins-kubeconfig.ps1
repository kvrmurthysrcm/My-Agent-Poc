$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$OutputFile = Join-Path $ProjectRoot "kubeconfig-jenkins"
$clusterName = kubectl config view --minify -o jsonpath='{.contexts[0].context.cluster}'
$server = kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}'
if (-not $clusterName) { throw "Unable to determine current Kubernetes cluster." }
if (-not $server) { throw "Unable to determine Kubernetes API server." }
$containerServer = $server -replace 'https://127\.0\.0\.1:', 'https://kubernetes.docker.internal:' -replace 'https://localhost:', 'https://kubernetes.docker.internal:'
kubectl config view --raw --minify --flatten | Set-Content -Encoding ascii $OutputFile
kubectl --kubeconfig=$OutputFile config set-cluster $clusterName --server=$containerServer --insecure-skip-tls-verify=true | Out-Null
kubectl --kubeconfig=$OutputFile config unset "clusters.$clusterName.certificate-authority" 2>$null | Out-Null
kubectl --kubeconfig=$OutputFile config unset "clusters.$clusterName.certificate-authority-data" 2>$null | Out-Null
Write-Host "Created: $OutputFile"
Write-Host "API: $containerServer"
docker cp $OutputFile "jenkins:/var/jenkins_home/kubeconfig-jenkins"
if ($LASTEXITCODE -ne 0) { throw "docker cp failed." }
docker exec -u root jenkins chown jenkins:jenkins /var/jenkins_home/kubeconfig-jenkins
if ($LASTEXITCODE -ne 0) { throw "chown failed." }
docker exec jenkins kubectl --kubeconfig=/var/jenkins_home/kubeconfig-jenkins get nodes -o wide
if ($LASTEXITCODE -ne 0) { throw "Jenkins Kubernetes verification failed." }
Write-Host "Jenkins kubeconfig installed and verified."
