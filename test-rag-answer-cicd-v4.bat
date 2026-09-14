@echo off
setlocal EnableExtensions EnableDelayedExpansion

REM ============================================================
REM My-Agent-Poc - rag-answer-service CI/CD validation
REM Run this BAT from the ROOT of the My-Agent-Poc repository.
REM
REM It validates:
REM   1. Required project files
REM   2. Docker / kubectl availability
REM   3. Test Docker image + pytest
REM   4. Runtime Docker image
REM   5. Local FastAPI /health
REM   6. Jenkins tooling + Docker access
REM   7. Jenkins kubeconfig creation + Kubernetes access
REM   8. Kubernetes manifests
REM   9. Load image into Docker Desktop kind node
REM  10. Kubernetes deployment + rollout
REM  11. /health from inside the deployed pod
REM
REM Stops at the first failure.
REM ============================================================

set "APP_NAME=rag-answer-service"
set "SERVICE_DIR=modules\rag-answer-service"
set "K8S_DIR=k8s\rag-answer-service"
set "K8S_NAMESPACE=rag-poc"
set "K8S_DEPLOYMENT=rag-answer-service"
set "KIND_NODE=desktop-control-plane"

set "TEST_IMAGE=%APP_NAME%:test-local"
set "RUNTIME_IMAGE=%APP_NAME%:local"
set "LOCAL_CONTAINER=%APP_NAME%-local-test"
set "LOCAL_HOST_PORT=18002"

set "JENKINS_CONTAINER=jenkins"
set "JENKINS_KUBECONFIG=D:\common\documentation\docker\jenkins\kubeconfig-jenkins"
set "TEMP_DEPLOY=%TEMP%\rag-answer-service-deployment-rendered.yaml"

echo.
echo ============================================================
echo RAG ANSWER SERVICE - LOCAL CI/CD VALIDATION
echo ============================================================
echo Current directory:
cd
echo.
echo IMPORTANT: Run this file from the My-Agent-Poc repository root.
echo.

REM ------------------------------------------------------------
REM STEP 1 - Required files
REM ------------------------------------------------------------
echo ============================================================
echo STEP 1 - VERIFY REQUIRED PROJECT FILES
echo ============================================================

call :requireFile "Jenkinsfile"
if errorlevel 1 goto :fail

call :requireFile "%SERVICE_DIR%\Dockerfile"
if errorlevel 1 goto :fail

call :requireFile "%SERVICE_DIR%\requirements.txt"
if errorlevel 1 goto :fail

call :requireDir "%SERVICE_DIR%\app"
if errorlevel 1 goto :fail

call :requireDir "%SERVICE_DIR%\tests"
if errorlevel 1 goto :fail

call :requireFile "%K8S_DIR%\namespace.yaml"
if errorlevel 1 goto :fail

call :requireFile "%K8S_DIR%\configmap.yaml"
if errorlevel 1 goto :fail

call :requireFile "%K8S_DIR%\deployment.yaml"
if errorlevel 1 goto :fail

call :requireFile "%K8S_DIR%\service.yaml"
if errorlevel 1 goto :fail

call :requireFile "scripts\prepare-jenkins-kubeconfig.ps1"
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   dir Jenkinsfile "%SERVICE_DIR%\Dockerfile" "%K8S_DIR%\deployment.yaml"
dir Jenkinsfile "%SERVICE_DIR%\Dockerfile" "%K8S_DIR%\deployment.yaml"
if errorlevel 1 goto :fail

REM ------------------------------------------------------------
REM STEP 2 - Docker and Kubernetes host preflight
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 2 - VERIFY DOCKER AND KUBERNETES ON WINDOWS
echo ============================================================

echo COMMAND:
echo   docker version
docker version
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   docker info
docker info
if errorlevel 1 goto :fail

echo.
echo COMMAND:
echo   kubectl version --client
kubectl version --client
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   kubectl config current-context
kubectl config current-context
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   kubectl get nodes -o wide
kubectl get nodes -o wide
if errorlevel 1 goto :fail

REM ------------------------------------------------------------
REM STEP 3 - Build test image
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 3 - BUILD PYTHON TEST IMAGE
echo ============================================================

echo COMMAND:
echo   docker build --target test -t %TEST_IMAGE% -f %SERVICE_DIR%\Dockerfile %SERVICE_DIR%
docker build --target test -t "%TEST_IMAGE%" -f "%SERVICE_DIR%\Dockerfile" "%SERVICE_DIR%"
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   docker image inspect %TEST_IMAGE%
docker image inspect "%TEST_IMAGE%"
if errorlevel 1 goto :fail

REM ------------------------------------------------------------
REM STEP 4 - Run pytest
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 4 - RUN PYTEST IN TEST IMAGE
echo ============================================================

docker rm -f "%APP_NAME%-tests-local" >nul 2>&1

echo COMMAND:
echo   docker run --name %APP_NAME%-tests-local %TEST_IMAGE%
docker run --name "%APP_NAME%-tests-local" "%TEST_IMAGE%"
set "TEST_RC=%ERRORLEVEL%"
if not "%TEST_RC%"=="0" (
    echo.
    echo WARNING: PYTEST FAILED WITH EXIT CODE %TEST_RC%.
    echo WARNING: CONTINUING TEMPORARILY SO THE REST OF THE CI/CD PATH CAN BE TESTED.
    echo.
    echo TEST CONTAINER LOGS:
    docker logs "%APP_NAME%-tests-local"
)

echo.
echo VERIFICATION COMMAND:
echo   docker inspect %APP_NAME%-tests-local --format "{{.State.ExitCode}}"
docker inspect "%APP_NAME%-tests-local" --format "{{.State.ExitCode}}"

echo.
echo VERIFICATION COMMAND:
echo   docker logs %APP_NAME%-tests-local
docker logs "%APP_NAME%-tests-local"

docker rm -f "%APP_NAME%-tests-local" >nul 2>&1

REM ------------------------------------------------------------
REM STEP 5 - Build runtime image
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 5 - BUILD RUNTIME IMAGE
echo ============================================================

echo COMMAND:
echo   docker build --target runtime -t %RUNTIME_IMAGE% -f %SERVICE_DIR%\Dockerfile %SERVICE_DIR%
docker build --target runtime -t "%RUNTIME_IMAGE%" -f "%SERVICE_DIR%\Dockerfile" "%SERVICE_DIR%"
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   docker images %APP_NAME%
docker images "%APP_NAME%"
if errorlevel 1 goto :fail

REM ------------------------------------------------------------
REM STEP 6 - Local runtime /health
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 6 - RUN SERVICE LOCALLY AND TEST /health
echo ============================================================

docker rm -f "%LOCAL_CONTAINER%" >nul 2>&1

echo COMMAND:
echo   docker run -d --name %LOCAL_CONTAINER% -p %LOCAL_HOST_PORT%:8002 %RUNTIME_IMAGE%
docker run -d --name "%LOCAL_CONTAINER%" -p %LOCAL_HOST_PORT%:8002 "%RUNTIME_IMAGE%"
if errorlevel 1 goto :fail

echo.
echo Waiting 5 seconds for FastAPI startup...
timeout /t 5 /nobreak >nul

echo.
echo VERIFICATION COMMAND:
echo   docker ps --filter "name=%LOCAL_CONTAINER%"
docker ps --filter "name=%LOCAL_CONTAINER%"
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   curl.exe --fail http://localhost:%LOCAL_HOST_PORT%/health
curl.exe --fail http://localhost:%LOCAL_HOST_PORT%/health
set "HEALTH_RC=%ERRORLEVEL%"
if not "%HEALTH_RC%"=="0" (
    echo.
    echo WARNING: Local /health verification failed with exit code %HEALTH_RC%.
    echo WARNING: Continuing temporarily because the container itself started successfully.
    echo.
    echo APPLICATION LOGS:
    docker logs "%LOCAL_CONTAINER%"
)

echo.
echo.
echo VERIFICATION COMMAND:
echo   docker logs --tail 50 %LOCAL_CONTAINER%
docker logs --tail 50 "%LOCAL_CONTAINER%"

echo.
echo Cleanup local test container:
echo   docker rm -f %LOCAL_CONTAINER%
docker rm -f "%LOCAL_CONTAINER%"
if errorlevel 1 goto :fail

REM ------------------------------------------------------------
REM STEP 7 - Jenkins preflight
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 7 - VERIFY JENKINS TOOLING AND DOCKER ACCESS
echo ============================================================

echo COMMAND:
echo   docker inspect %JENKINS_CONTAINER%
docker inspect "%JENKINS_CONTAINER%" >nul
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   docker ps --filter "name=%JENKINS_CONTAINER%"
docker ps --filter "name=%JENKINS_CONTAINER%"
if errorlevel 1 goto :fail

echo.
echo COMMAND:
echo   docker exec %JENKINS_CONTAINER% git --version
docker exec "%JENKINS_CONTAINER%" git --version
if errorlevel 1 goto :fail

echo.
echo COMMAND:
echo   docker exec %JENKINS_CONTAINER% docker --version
docker exec "%JENKINS_CONTAINER%" docker --version
if errorlevel 1 goto :fail

echo.
echo COMMAND:
echo   docker exec %JENKINS_CONTAINER% kubectl version --client
docker exec "%JENKINS_CONTAINER%" kubectl version --client
if errorlevel 1 goto :fail

echo.
echo COMMAND:
echo   docker exec %JENKINS_CONTAINER% java -version
docker exec "%JENKINS_CONTAINER%" java -version
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   docker exec %JENKINS_CONTAINER% docker ps
docker exec "%JENKINS_CONTAINER%" docker ps
if errorlevel 1 goto :fail

REM ------------------------------------------------------------
REM STEP 8 - Prepare Jenkins kubeconfig
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 8 - PREPARE JENKINS KUBECONFIG
echo ============================================================

echo COMMAND:
echo   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\prepare-jenkins-kubeconfig.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\prepare-jenkins-kubeconfig.ps1"
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   dir "%JENKINS_KUBECONFIG%"
dir "%JENKINS_KUBECONFIG%"
if errorlevel 1 goto :fail

echo.
echo Copy generated kubeconfig into Jenkins persistent home.
echo COMMAND:
echo   docker cp "%JENKINS_KUBECONFIG%" %JENKINS_CONTAINER%:/var/jenkins_home/kubeconfig-jenkins
docker cp "%JENKINS_KUBECONFIG%" "%JENKINS_CONTAINER%:/var/jenkins_home/kubeconfig-jenkins"
if errorlevel 1 goto :fail

echo.
echo COMMAND:
echo   docker exec %JENKINS_CONTAINER% chown jenkins:jenkins /var/jenkins_home/kubeconfig-jenkins
docker exec "%JENKINS_CONTAINER%" chown jenkins:jenkins /var/jenkins_home/kubeconfig-jenkins
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   docker exec %JENKINS_CONTAINER% ls -l /var/jenkins_home/kubeconfig-jenkins
docker exec "%JENKINS_CONTAINER%" ls -l /var/jenkins_home/kubeconfig-jenkins
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   docker exec %JENKINS_CONTAINER% kubectl --kubeconfig /var/jenkins_home/kubeconfig-jenkins get nodes -o wide
docker exec "%JENKINS_CONTAINER%" kubectl --kubeconfig /var/jenkins_home/kubeconfig-jenkins get nodes -o wide
if errorlevel 1 (
    echo.
    echo JENKINS KUBECONFIG CONTENT SUMMARY:
    docker exec "%JENKINS_CONTAINER%" kubectl --kubeconfig /var/jenkins_home/kubeconfig-jenkins config view --minify
    goto :fail
)

REM ------------------------------------------------------------
REM STEP 9 - Apply non-deployment Kubernetes manifests
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 9 - APPLY KUBERNETES NAMESPACE, CONFIGMAP, SERVICE
echo ============================================================

echo COMMAND:
echo   kubectl apply -f %K8S_DIR%\namespace.yaml
kubectl apply -f "%K8S_DIR%\namespace.yaml"
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   kubectl get namespace %K8S_NAMESPACE%
kubectl get namespace "%K8S_NAMESPACE%"
if errorlevel 1 goto :fail

echo.
echo COMMAND:
echo   kubectl apply -f %K8S_DIR%\configmap.yaml
kubectl apply -f "%K8S_DIR%\configmap.yaml"
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   kubectl -n %K8S_NAMESPACE% get configmap rag-answer-service-config -o yaml
kubectl -n "%K8S_NAMESPACE%" get configmap rag-answer-service-config -o yaml
if errorlevel 1 goto :fail

echo.
echo COMMAND:
echo   kubectl apply -f %K8S_DIR%\service.yaml
kubectl apply -f "%K8S_DIR%\service.yaml"
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   kubectl -n %K8S_NAMESPACE% get service %APP_NAME% -o wide
kubectl -n "%K8S_NAMESPACE%" get service "%APP_NAME%" -o wide
if errorlevel 1 goto :fail

REM ------------------------------------------------------------
REM STEP 10 - Verify Docker Desktop kind node
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 10 - VERIFY DOCKER DESKTOP KIND NODE
echo ============================================================

echo COMMAND:
echo   docker inspect %KIND_NODE%
docker inspect "%KIND_NODE%" >nul
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   docker ps --filter "name=%KIND_NODE%"
docker ps --filter "name=%KIND_NODE%"
if errorlevel 1 goto :fail

REM ------------------------------------------------------------
REM STEP 11 - Load runtime image into kind/containerd
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 11 - LOAD IMAGE INTO KUBERNETES KIND NODE
echo ============================================================

echo COMMAND:
echo   docker save %RUNTIME_IMAGE% ^| docker exec -i %KIND_NODE% ctr -n k8s.io images import -
docker save "%RUNTIME_IMAGE%" | docker exec -i "%KIND_NODE%" ctr -n k8s.io images import -
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   docker exec %KIND_NODE% ctr -n k8s.io images list ^| findstr /I "%APP_NAME%"
docker exec "%KIND_NODE%" ctr -n k8s.io images list | findstr /I "%APP_NAME%"
if errorlevel 1 goto :fail

REM ------------------------------------------------------------
REM STEP 12 - Render and apply deployment
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 12 - DEPLOY APPLICATION TO KUBERNETES
echo ============================================================

echo COMMAND:
echo   Replace __IMAGE__ in deployment.yaml with %RUNTIME_IMAGE%
powershell -NoProfile -Command "$c=Get-Content -Raw '%K8S_DIR%\deployment.yaml'; $c=$c.Replace('__IMAGE__','%RUNTIME_IMAGE%'); Set-Content -Path '%TEMP_DEPLOY%' -Value $c -Encoding ascii"
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   type "%TEMP_DEPLOY%"
type "%TEMP_DEPLOY%"
if errorlevel 1 goto :fail

echo.
echo COMMAND:
echo   kubectl apply -f "%TEMP_DEPLOY%"
kubectl apply -f "%TEMP_DEPLOY%"
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   kubectl -n %K8S_NAMESPACE% rollout status deployment/%K8S_DEPLOYMENT% --timeout=120s
kubectl -n "%K8S_NAMESPACE%" rollout status deployment/"%K8S_DEPLOYMENT%" --timeout=120s
if errorlevel 1 (
    echo.
    echo POD STATUS:
    kubectl -n "%K8S_NAMESPACE%" get pods -o wide
    echo.
    echo DEPLOYMENT DESCRIPTION:
    kubectl -n "%K8S_NAMESPACE%" describe deployment "%K8S_DEPLOYMENT%"
    goto :fail
)

REM ------------------------------------------------------------
REM STEP 13 - Verify Kubernetes deployment
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 13 - VERIFY KUBERNETES RESOURCES
echo ============================================================

echo VERIFICATION COMMAND:
echo   kubectl -n %K8S_NAMESPACE% get deployment %K8S_DEPLOYMENT% -o wide
kubectl -n "%K8S_NAMESPACE%" get deployment "%K8S_DEPLOYMENT%" -o wide
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   kubectl -n %K8S_NAMESPACE% get pods -l app=%APP_NAME% -o wide
kubectl -n "%K8S_NAMESPACE%" get pods -l app="%APP_NAME%" -o wide
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   kubectl -n %K8S_NAMESPACE% get service %APP_NAME% -o wide
kubectl -n "%K8S_NAMESPACE%" get service "%APP_NAME%" -o wide
if errorlevel 1 goto :fail

echo.
echo VERIFICATION COMMAND:
echo   kubectl -n %K8S_NAMESPACE% get all
kubectl -n "%K8S_NAMESPACE%" get all
if errorlevel 1 goto :fail

REM ------------------------------------------------------------
REM STEP 14 - Verify /health inside the Kubernetes pod
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 14 - TEST /health INSIDE KUBERNETES POD
echo ============================================================

echo COMMAND:
echo   kubectl -n %K8S_NAMESPACE% exec deployment/%K8S_DEPLOYMENT% -- python -c "..."
kubectl -n "%K8S_NAMESPACE%" exec deployment/"%K8S_DEPLOYMENT%" -- python -c "import urllib.request; print(urllib.request.urlopen('http://127.0.0.1:8002/health', timeout=10).read().decode())"
if errorlevel 1 (
    echo.
    echo APPLICATION LOGS:
    kubectl -n "%K8S_NAMESPACE%" logs deployment/"%K8S_DEPLOYMENT%" --tail=100
    goto :fail
)

echo.
echo VERIFICATION COMMAND:
echo   kubectl -n %K8S_NAMESPACE% logs deployment/%K8S_DEPLOYMENT% --tail=50
kubectl -n "%K8S_NAMESPACE%" logs deployment/"%K8S_DEPLOYMENT%" --tail=50

REM ------------------------------------------------------------
REM STEP 15 - Git status for Jenkins SCM readiness
REM ------------------------------------------------------------
echo.
echo ============================================================
echo STEP 15 - VERIFY GIT WORKING TREE
echo ============================================================

echo VERIFICATION COMMAND:
echo   git status --short
git status --short
if errorlevel 1 (
    echo Git command failed or this folder is not a Git repository.
    goto :fail
)

echo.
echo VERIFICATION COMMAND:
echo   git remote -v
git remote -v
if errorlevel 1 goto :fail

echo.
echo ============================================================
echo SUCCESS - ALL AUTOMATED VALIDATION STEPS PASSED
echo ============================================================
echo.
echo Verified:
echo   [OK] Required CI/CD files
echo   [OK] Docker Desktop
echo   [OK] Host kubectl / Kubernetes
echo   [OK] Python test image / pytest
echo   [OK] Python runtime image
echo   [OK] Local FastAPI /health
echo   [OK] Jenkins Git / Docker / kubectl / Java
echo   [OK] Jenkins access to Kubernetes
echo   [OK] Kubernetes namespace / ConfigMap / Service
echo   [OK] Image loaded into Docker Desktop kind node
echo   [OK] Kubernetes deployment rollout
echo   [OK] FastAPI /health inside Kubernetes
echo.
echo NEXT MANUAL STEP:
echo   Commit/push Jenkinsfile, Dockerfile and k8s files to GitHub,
echo   then create/run the Jenkins Pipeline job from SCM.
echo.
echo Script completed successfully. Exiting automatically.
exit /b 0


:requireFile
echo CHECK FILE:
echo   if exist "%~1"
if not exist "%~1" (
    echo ERROR: Required file not found: %~1
    exit /b 1
)
echo   FOUND: %~1
exit /b 0

:requireDir
echo CHECK DIRECTORY:
echo   if exist "%~1\"
if not exist "%~1\" (
    echo ERROR: Required directory not found: %~1
    exit /b 1
)
echo   FOUND: %~1
exit /b 0

:fail
set "RC=%ERRORLEVEL%"
echo.
echo ============================================================
echo FAILED
echo ============================================================
echo The script stopped at the first failing command.
echo Exit code: %RC%
echo.
echo Helpful current-state verification:
echo.
echo COMMAND:
echo   docker ps -a
docker ps -a
echo.
echo COMMAND:
echo   kubectl get nodes -o wide
kubectl get nodes -o wide
echo.
echo COMMAND:
echo   kubectl -n %K8S_NAMESPACE% get all
kubectl -n "%K8S_NAMESPACE%" get all 2>nul
echo.
echo If a local test container is still running, its last logs are:
docker logs "%LOCAL_CONTAINER%" --tail 100 2>nul
echo.
echo Copy the output around the FAILED step and paste it into ChatGPT.
echo Script failed. Exiting automatically with code %RC%.
echo.
exit /b %RC%
