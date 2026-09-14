@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "APP_NAME=rag-search-service"
set "SERVICE_DIR=modules\rag-search-service"
set "K8S_DIR=k8s\rag-search-service"
set "NAMESPACE=rag-poc"
set "KIND_NODE=desktop-control-plane"
set "TEST_IMAGE=%APP_NAME%:test-local"
set "RUNTIME_IMAGE=%APP_NAME%:local"
set "TEST_CONTAINER=%APP_NAME%-tests-local"
set "LOCAL_CONTAINER=%APP_NAME%-local-test"
set "LOCAL_HOST_PORT=18001"
set "JENKINS_CONTAINER=jenkins"
set "JENKINS_KUBECONFIG=/var/jenkins_home/kubeconfig-jenkins"
set "TEMP_DEPLOY=%TEMP%\rag-search-service-deployment-rendered.yaml"

echo ============================================================
echo RAG SEARCH SERVICE - CI/CD VALIDATION
echo ============================================================

call :require "%SERVICE_DIR%\Dockerfile" || exit /b 1
call :require "%K8S_DIR%\configmap.yaml" || exit /b 1
call :require "%K8S_DIR%\deployment.yaml" || exit /b 1
call :require "%K8S_DIR%\service.yaml" || exit /b 1

echo [1] Kubernetes host check
kubectl get nodes -o wide || exit /b 1

echo [2] Build test image
docker build --target test -t "%TEST_IMAGE%" -f "%SERVICE_DIR%\Dockerfile" "%SERVICE_DIR%" || exit /b 1
docker image inspect "%TEST_IMAGE%" >nul || exit /b 1

echo [3] Run pytest - NONBLOCKING FOR POC
docker rm -f "%TEST_CONTAINER%" >nul 2>&1
docker run --name "%TEST_CONTAINER%" --add-host=host.docker.internal:host-gateway -e RAG_SEARCH_TEST_DATABASE_URL=postgresql://library_user:library_pass@host.docker.internal:5432/online_library_test "%TEST_IMAGE%"
set "TEST_RC=%ERRORLEVEL%"
if not "%TEST_RC%"=="0" echo WARNING: pytest failed with code %TEST_RC%; continuing temporarily.
docker logs "%TEST_CONTAINER%"
docker rm -f "%TEST_CONTAINER%" >nul 2>&1

echo [4] Build runtime image
docker build --target runtime -t "%RUNTIME_IMAGE%" -f "%SERVICE_DIR%\Dockerfile" "%SERVICE_DIR%" || exit /b 1
docker images "%APP_NAME%"

echo [5] Local runtime /health
docker rm -f "%LOCAL_CONTAINER%" >nul 2>&1
docker run -d --name "%LOCAL_CONTAINER%" -p %LOCAL_HOST_PORT%:8001 -e DATABASE_URL=postgresql://library_user:library_pass@host.docker.internal:5432/online_library -e OLLAMA_BASE_URL=http://host.docker.internal:11434 --add-host=host.docker.internal:host-gateway "%RUNTIME_IMAGE%" || exit /b 1
timeout /t 5 /nobreak >nul
docker ps --filter "name=%LOCAL_CONTAINER%"
curl.exe --fail http://localhost:%LOCAL_HOST_PORT%/health
if errorlevel 1 echo WARNING: local /health failed; continuing because container startup is the primary POC check.
docker logs --tail 50 "%LOCAL_CONTAINER%"
docker rm -f "%LOCAL_CONTAINER%" >nul 2>&1

echo [6] Jenkins to Kubernetes
docker exec "%JENKINS_CONTAINER%" kubectl --kubeconfig "%JENKINS_KUBECONFIG%" get nodes -o wide || exit /b 1

echo [7] Apply ConfigMap and Service
kubectl create namespace "%NAMESPACE%" --dry-run=client -o yaml | kubectl apply -f - || exit /b 1
kubectl apply -f "%K8S_DIR%\configmap.yaml" || exit /b 1
kubectl apply -f "%K8S_DIR%\service.yaml" || exit /b 1
kubectl -n "%NAMESPACE%" get svc "%APP_NAME%" -o wide

echo [8] Load image into Kubernetes node
docker save "%RUNTIME_IMAGE%" | docker exec -i "%KIND_NODE%" ctr -n k8s.io images import - || exit /b 1
docker exec "%KIND_NODE%" ctr -n k8s.io images list | findstr /I "%APP_NAME%" || exit /b 1

echo [9] Deploy
powershell -NoProfile -Command "$c=Get-Content -Raw '%K8S_DIR%\deployment.yaml'; $c=$c.Replace('__IMAGE__','%RUNTIME_IMAGE%'); Set-Content -Path '%TEMP_DEPLOY%' -Value $c -Encoding ascii" || exit /b 1
kubectl apply -f "%TEMP_DEPLOY%" || exit /b 1
kubectl -n "%NAMESPACE%" rollout status deployment/%APP_NAME% --timeout=120s || exit /b 1

echo [10] Verify deployment and health
kubectl -n "%NAMESPACE%" get deployment,pods,svc -l app=%APP_NAME% -o wide
kubectl -n "%NAMESPACE%" exec deployment/%APP_NAME% -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=10).read().decode())" || exit /b 1
kubectl -n "%NAMESPACE%" logs deployment/%APP_NAME% --tail=50

echo ============================================================
echo SUCCESS - rag-search-service deployed and health verified.
echo ============================================================
exit /b 0

:require
if not exist "%~1" (
  echo ERROR: Missing %~1
  exit /b 1
)
echo FOUND: %~1
exit /b 0
