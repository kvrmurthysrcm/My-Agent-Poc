[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = "High")]
param(
    [ValidateRange(1, 100)]
    [int]$Keep = 3,
    [string]$Namespace = "rag-poc",
    [string]$Kubeconfig = "",
    [string]$KindNode = "desktop-control-plane",
    [switch]$Execute
)

$ErrorActionPreference = "Stop"

$services = @(
    @{ Repository = "rag-ingest-service"; Deployment = "rag-ingest-service" },
    @{ Repository = "rag-search-service"; Deployment = "rag-search-service" },
    @{ Repository = "rag-answer-service"; Deployment = "rag-answer-service" },
    @{ Repository = "online-library"; Deployment = "online-library" },
    @{ Repository = "secure-api"; Deployment = "secure-api" },
    @{ Repository = "online-library-mcp"; Deployment = "online-library-mcp" },
    @{ Repository = "online-library-agent"; Deployment = "online-library-agent" },
    @{ Repository = "weather-agent"; Deployment = "weather-agent" },
    @{ Repository = "weather-ai-agent"; Deployment = "weather-ai-agent" },
    @{ Repository = "angular-ui"; Deployment = "angular-ui" }
)

function Invoke-Kubectl([string[]]$Arguments) {
    $allArguments = @()
    if ($Kubeconfig) { $allArguments += @("--kubeconfig", $Kubeconfig) }
    $allArguments += $Arguments
    return (& kubectl @allArguments 2>$null)
}

function Get-DeployedImage([string]$Deployment) {
    $image = Invoke-Kubectl @(
        "-n", $Namespace, "get", "deployment", $Deployment,
        "-o", "jsonpath={.spec.template.spec.containers[0].image}"
    )
    if ($LASTEXITCODE -ne 0 -or -not $image) { return $null }
    return ([string]$image).Trim()
}

function Get-CiTags([string]$Repository) {
    $lines = & docker image ls $Repository --format '{{.Repository}}|{{.Tag}}' 2>$null
    if ($LASTEXITCODE -ne 0) { throw "Unable to list Docker images for $Repository." }

    return @($lines | ForEach-Object {
        $parts = $_ -split '\|', 2
        if ($parts.Count -eq 2 -and $parts[1] -match '^(?<build>\d+)-(?<sha>[0-9a-fA-F]{7,40})$') {
            [pscustomobject]@{
                Reference = "$($parts[0]):$($parts[1])"
                Build = [long]$Matches.build
            }
        }
    } | Sort-Object -Property Build, Reference -Descending)
}

function Remove-ContainerdReference([string]$Reference) {
    $nodeRunning = (& docker inspect -f '{{.State.Running}}' $KindNode 2>$null) -eq "true"
    if (-not $nodeRunning) {
        Write-Warning "Kubernetes node container '$KindNode' is unavailable; containerd cleanup skipped for $Reference."
        return
    }

    $qualified = if ($Reference -match '/') { $Reference } else { "docker.io/library/$Reference" }
    $knownReferences = @(& docker exec $KindNode ctr -n k8s.io images ls -q 2>$null)
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "Unable to list containerd images in '$KindNode'; skipped $Reference."
        return
    }

    foreach ($candidate in @($Reference, $qualified) | Select-Object -Unique) {
        if ($knownReferences -contains $candidate) {
            & docker exec $KindNode ctr -n k8s.io images rm $candidate | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "containerd failed to remove $candidate." }
        }
    }
}

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { throw "docker is not available on PATH." }
if (-not (Get-Command kubectl -ErrorAction SilentlyContinue)) { throw "kubectl is not available on PATH." }

$plannedRemovalCount = 0
foreach ($service in $services) {
    $repository = $service.Repository
    $deployedImage = Get-DeployedImage $service.Deployment
    if (-not $deployedImage) {
        Write-Warning "Deployment '$($service.Deployment)' was not found; skipping '$repository' for safety."
        continue
    }

    $images = @(Get-CiTags $repository)
    if ($images.Count -le $Keep) {
        Write-Host "[$repository] $($images.Count) CI image(s); nothing to remove."
        continue
    }

    $deployedMatch = @($images | Where-Object { $_.Reference -eq $deployedImage -or "docker.io/library/$($_.Reference)" -eq $deployedImage })
    if ($deployedMatch.Count -ne 1) {
        Write-Warning "Deployed image '$deployedImage' is not an unambiguous local CI tag; skipping '$repository' for safety."
        continue
    }

    # The active image always consumes one of the Keep slots. Fill the remaining
    # slots with the newest tags so the total never exceeds Keep.
    $retained = @($deployedMatch[0].Reference)
    foreach ($image in $images) {
        if ($retained.Count -ge $Keep) { break }
        if ($retained -notcontains $image.Reference) { $retained += $image.Reference }
    }
    $remove = @($images | Where-Object { $retained -notcontains $_.Reference })

    Write-Host "[$repository] deployed=$deployedImage keep=$($retained -join ', ') remove=$($remove.Reference -join ', ')"
    foreach ($image in $remove) {
        $plannedRemovalCount++
        if ($Execute -and $PSCmdlet.ShouldProcess($image.Reference, "Remove CI image from Docker and Kubernetes node containerd")) {
            # Remove the node reference first; the host tag remains available if this step fails.
            Remove-ContainerdReference $image.Reference
            & docker image rm $image.Reference | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "Docker failed to remove $($image.Reference)." }
        }
    }

    # Test-stage images are ephemeral and are never deployed, so retaining them
    # only consumes disk without providing rollback value.
    $testLines = & docker image ls $repository --format '{{.Repository}}|{{.Tag}}' 2>$null
    $testImages = @($testLines | ForEach-Object {
        $parts = $_ -split '\|', 2
        if ($parts.Count -eq 2 -and $parts[1] -match '^test-\d+-[0-9a-fA-F]{7,40}$') {
            "$($parts[0]):$($parts[1])"
        }
    })
    foreach ($testImage in $testImages) {
        $plannedRemovalCount++
        if ($Execute -and $PSCmdlet.ShouldProcess($testImage, "Remove ephemeral CI test image from Docker")) {
            & docker image rm $testImage | Out-Host
            if ($LASTEXITCODE -ne 0) { throw "Docker failed to remove $testImage." }
        }
    }
}

if (-not $Execute) {
    Write-Host "Preview complete: $plannedRemovalCount image tag(s) are eligible. Re-run with -Execute to remove them."
} else {
    Write-Host "Cleanup complete: processed $plannedRemovalCount eligible image tag(s); at most $Keep CI tags are retained per service."
}
