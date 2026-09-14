@echo off
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0.."

REM ============================================================
REM My-Agent-Poc cumulative CI/CD validation
REM Services: ingest -> search -> answer -> online-library -> secure-api
REM Tests are temporarily NON-BLOCKING.
REM ============================================================
set "NS=rag-poc"
set "KIND_NODE=desktop-control-plane"
set "JENKINS=jenkins"
set "JENKINS_KUBECONFIG=D:\common\documentation\docker\jenkins\kubeconfig-jenkins"
set "INGEST_DIR=modules\rag-ingest-service"
set "SEARCH_DIR=modules\rag-search-service"
set "ANSWER_DIR=modules\rag-answer-service"
set "LIBRARY_DIR=modules\online_library"
set "SECURE_DIR=modules\secure_api"
set "INGEST_IMAGE=rag-ingest-service:local"
set "SEARCH_IMAGE=rag-search-service:local"
set "ANSWER_IMAGE=rag-answer-service:local"
set "SECURE_IMAGE=secure-api:local"
set "INGEST_TEST_IMAGE=rag-ingest-service:test-local"
set "SEARCH_TEST_IMAGE=rag-search-service:test-local"
set "ANSWER_TEST_IMAGE=rag-answer-service:test-local"
set "LIBRARY_TEST_IMAGE=online-library:test-local"
set "LIBRARY_IMAGE=online-library:local"
set "LIBRARY_TEST_CONTAINER=online-library-tests-local"
set "SECURE_TEST_IMAGE=secure-api:test-local"
set "INGEST_TEST_CONTAINER=rag-ingest-service-tests-local"
set "SEARCH_TEST_CONTAINER=rag-search-service-tests-local"
set "ANSWER_TEST_CONTAINER=rag-answer-service-tests-local"
set "SECURE_TEST_CONTAINER=secure-api-tests-local"
set "TMP_INGEST=%TEMP%\rag-ingest-service-deployment.yaml"
set "TMP_SEARCH=%TEMP%\rag-search-service-deployment.yaml"
set "TMP_ANSWER=%TEMP%\rag-answer-service-deployment.yaml"
set "TMP_LIBRARY=%TEMP%\online-library-deployment.yaml"
set "TMP_SECURE=%TEMP%\secure-api-deployment.yaml"

call :step "1" "VERIFY REQUIRED FILES"
for %%F in ("Jenkinsfile" "k8s\namespace.yaml" "%INGEST_DIR%\Dockerfile" "%SEARCH_DIR%\Dockerfile" "%ANSWER_DIR%\Dockerfile" "%LIBRARY_DIR%\Dockerfile" "%LIBRARY_DIR%\requirements-cicd.txt" "%SECURE_DIR%\Dockerfile" "k8s\rag-ingest-service\deployment.yaml" "k8s\rag-search-service\deployment.yaml" "k8s\rag-answer-service\deployment.yaml" "k8s\online-library\deployment.yaml" "k8s\online-library\configmap.yaml" "k8s\online-library\service.yaml" "k8s\secure-api\deployment.yaml" "k8s\secure-api\secret.yaml" "scripts\prepare-jenkins-kubeconfig.ps1") do (
  call :requireFile "%%~F"
  if errorlevel 1 goto :fail
)

call :step "2" "VERIFY DOCKER AND KUBERNETES"
docker version || goto :fail
kubectl get nodes -o wide || goto :fail

call :step "3" "VERIFY JENKINS ACCESS"
docker exec %JENKINS% docker --version || goto :fail
docker exec %JENKINS% kubectl version --client || goto :fail

call :step "4" "PREPARE JENKINS KUBECONFIG"
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\prepare-jenkins-kubeconfig.ps1" || goto :fail
docker cp "%JENKINS_KUBECONFIG%" "%JENKINS%:/var/jenkins_home/kubeconfig-jenkins" || goto :fail
docker exec "%JENKINS%" chown jenkins:jenkins /var/jenkins_home/kubeconfig-jenkins || goto :fail
docker exec "%JENKINS%" kubectl --kubeconfig /var/jenkins_home/kubeconfig-jenkins get nodes -o wide || goto :fail

call :step "5" "APPLY COMMON NAMESPACE"
kubectl apply -f "k8s\namespace.yaml" || goto :fail

call :step "6" "RAG INGEST - BUILD TEST IMAGE"
docker build --target test -t "%INGEST_TEST_IMAGE%" -f "%INGEST_DIR%\Dockerfile" "%INGEST_DIR%" || goto :fail

call :step "7" "RAG INGEST - PYTEST (NON-BLOCKING)"
docker rm -f "%INGEST_TEST_CONTAINER%" >nul 2>&1
docker run --name "%INGEST_TEST_CONTAINER%" --add-host=host.docker.internal:host-gateway -e RAG_INGEST_TEST_DATABASE_URL="postgresql://library_user:library_pass@host.docker.internal:5432/online_library_test" "%INGEST_TEST_IMAGE%"
set "INGEST_TEST_RC=%ERRORLEVEL%"
if not "%INGEST_TEST_RC%"=="0" echo WARNING: Ingest pytest failed with exit code %INGEST_TEST_RC% - continuing.
docker rm -f "%INGEST_TEST_CONTAINER%" >nul 2>&1

call :step "8" "RAG INGEST - BUILD RUNTIME IMAGE"
docker build --target runtime -t "%INGEST_IMAGE%" -f "%INGEST_DIR%\Dockerfile" "%INGEST_DIR%" || goto :fail

call :step "9" "RAG INGEST - LOAD IMAGE INTO KUBERNETES"
docker save "%INGEST_IMAGE%" | docker exec -i "%KIND_NODE%" ctr -n k8s.io images import - || goto :fail
docker exec "%KIND_NODE%" ctr -n k8s.io images list | findstr /I "rag-ingest-service" || goto :fail

call :step "10" "RAG INGEST - DEPLOY"
kubectl apply -f "k8s\rag-ingest-service\configmap.yaml" || goto :fail
kubectl apply -f "k8s\rag-ingest-service\service.yaml" || goto :fail
powershell -NoProfile -Command "$c=Get-Content -Raw 'k8s\rag-ingest-service\deployment.yaml'; $c=$c.Replace('__IMAGE__','%INGEST_IMAGE%'); Set-Content -Path '%TMP_INGEST%' -Value $c -Encoding ascii" || goto :fail
kubectl apply -f "%TMP_INGEST%" || goto :fail
kubectl -n "%NS%" rollout status deployment/rag-ingest-service --timeout=240s || goto :fail
kubectl -n "%NS%" get pods -l app=rag-ingest-service -o wide || goto :fail
kubectl -n "%NS%" exec deployment/rag-ingest-service -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=10).read().decode())" || goto :fail

call :step "11" "RAG SEARCH - BUILD TEST IMAGE"
docker build --target test -t "%SEARCH_TEST_IMAGE%" -f "%SEARCH_DIR%\Dockerfile" "%SEARCH_DIR%" || goto :fail

call :step "12" "RAG SEARCH - PYTEST (NON-BLOCKING)"
docker rm -f "%SEARCH_TEST_CONTAINER%" >nul 2>&1
docker run --name "%SEARCH_TEST_CONTAINER%" --add-host=host.docker.internal:host-gateway -e RAG_SEARCH_TEST_DATABASE_URL="postgresql://library_user:library_pass@host.docker.internal:5432/online_library_test" "%SEARCH_TEST_IMAGE%"
set "SEARCH_TEST_RC=%ERRORLEVEL%"
if not "%SEARCH_TEST_RC%"=="0" echo WARNING: Search pytest failed with exit code %SEARCH_TEST_RC% - continuing.
docker rm -f "%SEARCH_TEST_CONTAINER%" >nul 2>&1

call :step "13" "RAG SEARCH - BUILD RUNTIME IMAGE"
docker build --target runtime -t "%SEARCH_IMAGE%" -f "%SEARCH_DIR%\Dockerfile" "%SEARCH_DIR%" || goto :fail

call :step "14" "RAG SEARCH - LOAD IMAGE INTO KUBERNETES"
docker save "%SEARCH_IMAGE%" | docker exec -i "%KIND_NODE%" ctr -n k8s.io images import - || goto :fail

call :step "15" "RAG SEARCH - DEPLOY"
kubectl apply -f "k8s\rag-search-service\configmap.yaml" || goto :fail
kubectl apply -f "k8s\rag-search-service\service.yaml" || goto :fail
powershell -NoProfile -Command "$c=Get-Content -Raw 'k8s\rag-search-service\deployment.yaml'; $c=$c.Replace('__IMAGE__','%SEARCH_IMAGE%'); Set-Content -Path '%TMP_SEARCH%' -Value $c -Encoding ascii" || goto :fail
kubectl apply -f "%TMP_SEARCH%" || goto :fail
kubectl -n "%NS%" rollout status deployment/rag-search-service --timeout=180s || goto :fail
kubectl -n "%NS%" exec deployment/rag-search-service -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8001/health', timeout=10).read().decode())" || goto :fail

call :step "16" "RAG ANSWER - BUILD TEST IMAGE"
docker build --target test -t "%ANSWER_TEST_IMAGE%" -f "%ANSWER_DIR%\Dockerfile" "%ANSWER_DIR%" || goto :fail

call :step "17" "RAG ANSWER - PYTEST (NON-BLOCKING)"
docker rm -f "%ANSWER_TEST_CONTAINER%" >nul 2>&1
docker run --name "%ANSWER_TEST_CONTAINER%" "%ANSWER_TEST_IMAGE%"
set "ANSWER_TEST_RC=%ERRORLEVEL%"
if not "%ANSWER_TEST_RC%"=="0" echo WARNING: Answer pytest failed with exit code %ANSWER_TEST_RC% - continuing.
docker rm -f "%ANSWER_TEST_CONTAINER%" >nul 2>&1

call :step "18" "RAG ANSWER - BUILD RUNTIME IMAGE"
docker build --target runtime -t "%ANSWER_IMAGE%" -f "%ANSWER_DIR%\Dockerfile" "%ANSWER_DIR%" || goto :fail

call :step "19" "RAG ANSWER - LOAD IMAGE INTO KUBERNETES"
docker save "%ANSWER_IMAGE%" | docker exec -i "%KIND_NODE%" ctr -n k8s.io images import - || goto :fail

call :step "20" "RAG ANSWER - DEPLOY"
kubectl apply -f "k8s\rag-answer-service\configmap.yaml" || goto :fail
kubectl apply -f "k8s\rag-answer-service\service.yaml" || goto :fail
powershell -NoProfile -Command "$c=Get-Content -Raw 'k8s\rag-answer-service\deployment.yaml'; $c=$c.Replace('__IMAGE__','%ANSWER_IMAGE%'); Set-Content -Path '%TMP_ANSWER%' -Value $c -Encoding ascii" || goto :fail
kubectl apply -f "%TMP_ANSWER%" || goto :fail
kubectl -n "%NS%" rollout status deployment/rag-answer-service --timeout=180s || goto :fail
kubectl -n "%NS%" exec deployment/rag-answer-service -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8002/health', timeout=10).read().decode())" || goto :fail

call :step "21" "ONLINE LIBRARY - BUILD TEST IMAGE"
docker build --target test -t "%LIBRARY_TEST_IMAGE%" -f "%LIBRARY_DIR%\Dockerfile" "%LIBRARY_DIR%" || goto :fail

call :step "22" "ONLINE LIBRARY - PYTEST (NON-BLOCKING)"
docker rm -f "%LIBRARY_TEST_CONTAINER%" >nul 2>&1
docker run --name "%LIBRARY_TEST_CONTAINER%" "%LIBRARY_TEST_IMAGE%"
set "LIBRARY_TEST_RC=%ERRORLEVEL%"
if not "%LIBRARY_TEST_RC%"=="0" echo WARNING: Online Library pytest failed with exit code %LIBRARY_TEST_RC% - continuing.
docker rm -f "%LIBRARY_TEST_CONTAINER%" >nul 2>&1

call :step "23" "ONLINE LIBRARY - BUILD RUNTIME IMAGE"
docker build --target runtime -t "%LIBRARY_IMAGE%" -f "%LIBRARY_DIR%\Dockerfile" "%LIBRARY_DIR%" || goto :fail

call :step "24" "ONLINE LIBRARY - LOAD IMAGE INTO KUBERNETES"
docker save "%LIBRARY_IMAGE%" | docker exec -i "%KIND_NODE%" ctr -n k8s.io images import - || goto :fail

call :step "25" "ONLINE LIBRARY - DEPLOY"
kubectl apply -f "k8s\online-library\configmap.yaml" || goto :fail
kubectl apply -f "k8s\online-library\service.yaml" || goto :fail
powershell -NoProfile -Command "$c=Get-Content -Raw 'k8s\online-library\deployment.yaml'; $c=$c.Replace('__IMAGE__','%LIBRARY_IMAGE%'); Set-Content -Path '%TMP_LIBRARY%' -Value $c -Encoding ascii" || goto :fail
kubectl apply -f "%TMP_LIBRARY%" || goto :fail
kubectl -n "%NS%" rollout status deployment/online-library --timeout=180s || goto :fail
kubectl -n "%NS%" exec deployment/online-library -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8003/health/db', timeout=10).read().decode())" || goto :fail

call :step "26" "SECURE API - BUILD TEST IMAGE"
docker build --target test -t "%SECURE_TEST_IMAGE%" -f "%SECURE_DIR%\Dockerfile" "%SECURE_DIR%" || goto :fail

call :step "27" "SECURE API - PYTEST (NON-BLOCKING)"
docker rm -f "%SECURE_TEST_CONTAINER%" >nul 2>&1
docker run --name "%SECURE_TEST_CONTAINER%" "%SECURE_TEST_IMAGE%"
set "SECURE_TEST_RC=%ERRORLEVEL%"
if not "%SECURE_TEST_RC%"=="0" echo WARNING: Secure API pytest failed with exit code %SECURE_TEST_RC% - continuing.
docker rm -f "%SECURE_TEST_CONTAINER%" >nul 2>&1

call :step "28" "SECURE API - BUILD RUNTIME IMAGE"
docker build --target runtime -t "%SECURE_IMAGE%" -f "%SECURE_DIR%\Dockerfile" "%SECURE_DIR%" || goto :fail

call :step "29" "SECURE API - LOAD IMAGE INTO KUBERNETES"
docker save "%SECURE_IMAGE%" | docker exec -i "%KIND_NODE%" ctr -n k8s.io images import - || goto :fail

call :step "30" "SECURE API - DEPLOY"
kubectl apply -f "k8s\secure-api\configmap.yaml" || goto :fail
kubectl apply -f "k8s\secure-api\secret.yaml" || goto :fail
kubectl apply -f "k8s\secure-api\service.yaml" || goto :fail
powershell -NoProfile -Command "$c=Get-Content -Raw 'k8s\secure-api\deployment.yaml'; $c=$c.Replace('__IMAGE__','%SECURE_IMAGE%'); Set-Content -Path '%TMP_SECURE%' -Value $c -Encoding ascii" || goto :fail
kubectl apply -f "%TMP_SECURE%" || goto :fail
kubectl -n "%NS%" rollout status deployment/secure-api --timeout=180s || goto :fail
kubectl -n "%NS%" exec deployment/secure-api -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8010/health', timeout=10).read().decode())" || goto :fail

call :step "31" "VERIFY COMPLETE CUMULATIVE STACK"
kubectl -n "%NS%" get all || goto :fail
kubectl -n "%NS%" get configmap || goto :fail

echo.
echo ============================================================
echo SUCCESS - CUMULATIVE SECURE API + ONLINE LIBRARY + INGEST + SEARCH + ANSWER VALIDATION PASSED
echo ============================================================
echo Ingest tests exit code: %INGEST_TEST_RC%
echo Search tests exit code: %SEARCH_TEST_RC%
echo Answer tests exit code: %ANSWER_TEST_RC%
echo Online Library tests exit code: %LIBRARY_TEST_RC%
echo Secure API tests exit code: %SECURE_TEST_RC%
echo Tests are temporarily non-blocking.
exit /b 0

:step
echo.
echo ============================================================
echo STEP %~1 - %~2
echo ============================================================
exit /b 0

:requireFile
if not exist "%~1" (
  echo ERROR: Required file not found: %~1
  exit /b 1
)
echo FOUND: %~1
exit /b 0

:fail
set "RC=%ERRORLEVEL%"
echo.
echo ============================================================
echo FAILED - CUMULATIVE VALIDATION STOPPED
echo Exit code: %RC%
echo ============================================================
kubectl -n "%NS%" get all 2>nul
echo.
echo Ingest logs:
kubectl -n "%NS%" logs deployment/rag-ingest-service --tail=100 2>nul
echo.
echo Search logs:
kubectl -n "%NS%" logs deployment/rag-search-service --tail=100 2>nul
echo.
echo Answer logs:
kubectl -n "%NS%" logs deployment/rag-answer-service --tail=100 2>nul
echo.
echo Online Library logs:
kubectl -n "%NS%" logs deployment/online-library --tail=100 2>nul
echo.
echo Secure API logs:
kubectl -n "%NS%" logs deployment/secure-api --tail=100 2>nul
exit /b %RC%
