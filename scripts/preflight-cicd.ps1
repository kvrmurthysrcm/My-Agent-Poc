param(
    [string]$Namespace = "rag-poc",
    [string]$ExpectedKubeContext = "docker-desktop",
    [string]$JenkinsContainer = "",
    [string]$PostgresHost = "localhost",
    [int]$PostgresPort = 5432,
    [string]$KeycloakHost = "localhost",
    [int]$KeycloakPort = 8080,
    [string]$OllamaHost = "localhost",
    [int]$OllamaPort = 11434,
    [switch]$RequireNamespace
)

$ProjectRoot = (Get-Item -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '..')).FullName
$exitCode = 1

# Resolve paths from this script rather than from the caller's current
# directory, so this works when launched directly from scripts/.
Push-Location -LiteralPath $ProjectRoot
try {
    $ErrorActionPreference = "Continue"
    $script:Failures = 0
    $script:Warnings = 0

function Write-Section([string]$Title) {
    Write-Host "`n============================================================" -ForegroundColor Cyan
    Write-Host $Title -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
}

function Pass([string]$Message) { Write-Host "[PASS] $Message" -ForegroundColor Green }
function Warn([string]$Message) { $script:Warnings++; Write-Host "[WARN] $Message" -ForegroundColor Yellow }
function Fail([string]$Message) { $script:Failures++; Write-Host "[FAIL] $Message" -ForegroundColor Red }
function Info([string]$Message) { Write-Host "[INFO] $Message" -ForegroundColor Gray }

function Command-Exists([string]$Name) {
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Test-Tcp([string]$HostName, [int]$Port, [int]$TimeoutMs = 2500) {
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $iar = $client.BeginConnect($HostName, $Port, $null, $null)
        if (-not $iar.AsyncWaitHandle.WaitOne($TimeoutMs, $false)) {
            $client.Close(); return $false
        }
        $client.EndConnect($iar); $client.Close(); return $true
    } catch { return $false }
}

Write-Host "CI/CD PRE-FLIGHT VALIDATION" -ForegroundColor White
Write-Host "Repository root: $ProjectRoot" -ForegroundColor Gray
Write-Host "This script can be launched from scripts/ or any other working directory before git push." -ForegroundColor Gray

# ------------------------------------------------------------
Write-Section "1. Git / GitHub"

if (Command-Exists "git") {
    Pass "git is installed: $(git --version)"
} else {
    Fail "git is not available in PATH."
}

if (Command-Exists "git") {
    $insideRepo = git rev-parse --is-inside-work-tree 2>$null
    if ($insideRepo -eq "true") {
        Pass "Current directory is a Git working tree."
        $branch = git branch --show-current 2>$null
        $sha = git rev-parse --short HEAD 2>$null
        Info "Branch: $branch"
        Info "Current commit: $sha"

        $remote = git remote get-url origin 2>$null
        if ($LASTEXITCODE -eq 0 -and $remote) {
            Pass "origin is configured: $remote"
            git ls-remote --exit-code origin HEAD *> $null
            if ($LASTEXITCODE -eq 0) { Pass "GitHub/origin is reachable and credentials are sufficient for read access." }
            else { Fail "Cannot reach/read origin. Check network/GitHub credentials." }
        } else {
            Fail "No origin remote is configured."
        }

        $status = git status --porcelain
        if ($status) {
            Warn "Working tree has uncommitted changes. Review them before committing/pushing."
            git status --short
        } else {
            Pass "Working tree is clean."
        }
    } else {
        Fail "Run this script from the Git repository root."
    }
}

# ------------------------------------------------------------
Write-Section "2. Docker Desktop / Docker Engine"

if (-not (Command-Exists "docker")) {
    Fail "docker CLI is not available in PATH."
} else {
    Pass "docker CLI is installed: $(docker --version)"
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        Pass "Docker engine is running and responding."
        $containers = docker ps --format "{{.Names}}|{{.Image}}|{{.Status}}"
        if ($containers) {
            Info "Running containers:"
            $containers | ForEach-Object { Write-Host "       $_" -ForegroundColor DarkGray }
        } else {
            Warn "Docker is running, but there are no running containers."
        }
    } else {
        Fail "Docker engine is not responding. Start Docker Desktop."
    }
}

# ------------------------------------------------------------
Write-Section "3. Kubernetes"

if (-not (Command-Exists "kubectl")) {
    Fail "kubectl is not available in PATH."
} else {
    Pass "kubectl is installed: $((kubectl version --client --output=yaml 2>$null | Select-String 'gitVersion:' | Select-Object -First 1).ToString().Trim())"

    $ctx = kubectl config current-context 2>$null
    if ($LASTEXITCODE -eq 0 -and $ctx) {
        Info "Current Kubernetes context: $ctx"
        if ($ExpectedKubeContext -and $ctx -ne $ExpectedKubeContext) {
            Warn "Expected context '$ExpectedKubeContext' but current context is '$ctx'. Verify before deploying."
        } else {
            Pass "Kubernetes context is as expected."
        }
    } else {
        Fail "No usable Kubernetes context found."
    }

    kubectl cluster-info *> $null
    if ($LASTEXITCODE -eq 0) {
        Pass "Kubernetes API server is reachable."
    } else {
        Fail "Kubernetes API server is not reachable. Enable Kubernetes in Docker Desktop."
    }

    $nodeLines = kubectl get nodes --no-headers 2>$null
    if ($LASTEXITCODE -eq 0 -and $nodeLines) {
        $notReady = @($nodeLines | Where-Object { $_ -notmatch '\sReady\s' -and $_ -notmatch '\sReady,' })
        if ($notReady.Count -eq 0) { Pass "All Kubernetes nodes are Ready." }
        else { Fail "One or more Kubernetes nodes are not Ready:`n$($notReady -join "`n")" }
        kubectl get nodes
    } else {
        Fail "Unable to query Kubernetes nodes."
    }

    kubectl get namespace $Namespace *> $null
    if ($LASTEXITCODE -eq 0) {
        Pass "Namespace '$Namespace' exists."
        Info "Current workloads in ${Namespace}:"
        kubectl -n $Namespace get pods,deploy,svc 2>$null
    } elseif ($RequireNamespace) {
        Fail "Namespace '$Namespace' does not exist."
    } else {
        Warn "Namespace '$Namespace' does not exist yet. This is OK if Jenkins creates/applies it during the pipeline."
    }
}

# ------------------------------------------------------------
Write-Section "4. Jenkins container and Jenkins-to-Docker/Kubernetes access"

if (Command-Exists "docker") {
    if (-not $JenkinsContainer) {
        $candidate = docker ps --format "{{.Names}}|{{.Image}}" 2>$null |
            Where-Object { $_ -match '(?i)jenkins' } |
            Select-Object -First 1
        if ($candidate) { $JenkinsContainer = ($candidate -split '\|')[0] }
    }

    if ($JenkinsContainer) {
        $running = docker inspect -f '{{.State.Running}}' $JenkinsContainer 2>$null
        if ($running -eq "true") {
            Pass "Jenkins container '$JenkinsContainer' is running."

            $ports = docker port $JenkinsContainer 2>$null
            if ($ports) { Info "Published Jenkins ports:`n$ports" }

            docker exec $JenkinsContainer git --version *> $null
            if ($LASTEXITCODE -eq 0) { Pass "Jenkins container can execute git." }
            else { Fail "git is unavailable inside Jenkins container." }

            docker exec $JenkinsContainer docker info *> $null
            if ($LASTEXITCODE -eq 0) { Pass "Jenkins container can access the Docker engine." }
            else { Fail "Jenkins container cannot access Docker. Check Docker socket/CLI configuration." }

            docker exec $JenkinsContainer kubectl version --client *> $null
            if ($LASTEXITCODE -eq 0) { Pass "kubectl is installed inside Jenkins container." }
            else { Fail "kubectl is unavailable inside Jenkins container." }

            docker exec $JenkinsContainer sh -c 'test -f /var/jenkins_home/kubeconfig-jenkins' *> $null
            if ($LASTEXITCODE -eq 0) {
                Pass "Jenkins kubeconfig exists: /var/jenkins_home/kubeconfig-jenkins"
                docker exec $JenkinsContainer sh -c 'kubectl --kubeconfig /var/jenkins_home/kubeconfig-jenkins get nodes' 2>$null
                if ($LASTEXITCODE -eq 0) { Pass "Jenkins can reach Kubernetes using its kubeconfig." }
                else { Fail "Jenkins kubeconfig exists, but Jenkins cannot reach Kubernetes." }
            } else {
                Fail "Jenkins kubeconfig is missing at /var/jenkins_home/kubeconfig-jenkins."
            }
        } else {
            Fail "Jenkins container '$JenkinsContainer' is not running."
        }
    } else {
        Fail "Could not detect a running Jenkins container. Pass -JenkinsContainer <name> if its name/image does not contain 'jenkins'."
    }
}

# ------------------------------------------------------------
Write-Section "5. POC host dependencies"

if (Test-Tcp $PostgresHost $PostgresPort) { Pass "PostgreSQL TCP endpoint reachable at ${PostgresHost}:$PostgresPort." }
else { Fail "PostgreSQL is not reachable at ${PostgresHost}:$PostgresPort." }

if (Test-Tcp $KeycloakHost $KeycloakPort) { Pass "Keycloak TCP endpoint reachable at ${KeycloakHost}:$KeycloakPort." }
else { Fail "Keycloak is not reachable at ${KeycloakHost}:$KeycloakPort." }

if (Test-Tcp $OllamaHost $OllamaPort) {
    Pass "Ollama endpoint reachable at ${OllamaHost}:$OllamaPort."
    if (Command-Exists "ollama") {
        $ollamaList = ollama list 2>$null
        if ($LASTEXITCODE -eq 0) {
            Info "Ollama models:"
            $ollamaList | ForEach-Object { Write-Host "       $_" -ForegroundColor DarkGray }
        }
    }
} else { Fail "Ollama is not reachable at ${OllamaHost}:$OllamaPort." }

# ------------------------------------------------------------
Write-Section "6. Final result"

if ($script:Failures -eq 0) {
    Pass "PRE-FLIGHT PASSED. Critical prerequisites are ready."
    if ($script:Warnings -gt 0) { Warn "$($script:Warnings) warning(s) were reported; review them before push." }
    Write-Host "`nYou can now commit/push and then monitor Jenkins without clicking Build Now." -ForegroundColor Green
    $exitCode = 0
} else {
    Fail "PRE-FLIGHT FAILED: $($script:Failures) critical check(s) failed; $($script:Warnings) warning(s)."
    Write-Host "Fix the failures before pushing if you want the CI/CD test to be meaningful." -ForegroundColor Red
    $exitCode = 1
}
}
finally {
    Pop-Location
}

exit $exitCode
