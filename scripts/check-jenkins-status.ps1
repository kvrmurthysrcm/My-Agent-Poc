# Jenkins REST API Status Checker
# Fill in the variables below, then run this script in PowerShell.

# =========================
# USER CONFIGURATION
# =========================

$JenkinsUrl = "http://localhost:9090"
$Username   = "admin"
$Password   = "admin123"

# Optional: if you know the job/pipeline name, set it here.
# Leave blank to inspect all jobs only.
$JobName    = ""

# =========================
# SCRIPT
# =========================

$ErrorActionPreference = "Stop"

function Write-Section($title) {
    Write-Host ""
    Write-Host ("=" * 70)
    Write-Host $title
    Write-Host ("=" * 70)
}

function New-BasicAuthHeader($user, $pass) {
    $pair = "{0}:{1}" -f $user, $pass
    $bytes = [System.Text.Encoding]::ASCII.GetBytes($pair)
    $token = [Convert]::ToBase64String($bytes)
    return @{ Authorization = "Basic $token" }
}

$Headers = New-BasicAuthHeader $Username $Password

try {
    Write-Section "1. Jenkins Server Status"

    $server = Invoke-RestMethod `
        -Uri "$JenkinsUrl/api/json" `
        -Headers $Headers

    Write-Host "[PASS] Jenkins API is reachable."
    Write-Host "Node Description : $($server.nodeDescription)"
    Write-Host "Mode             : $($server.mode)"
    Write-Host "Executors        : $($server.numExecutors)"
    Write-Host "Quieting Down    : $($server.quietingDown)"

    Write-Section "2. Jenkins Jobs / Pipelines"

    $jobsResponse = Invoke-RestMethod `
        -Uri "$JenkinsUrl/api/json?tree=jobs[name,url,color,_class]" `
        -Headers $Headers

    if (-not $jobsResponse.jobs -or $jobsResponse.jobs.Count -eq 0) {
        Write-Warning "No Jenkins jobs/pipelines were found."
    }
    else {
        $jobsResponse.jobs |
            Select-Object name, color, _class, url |
            Format-Table -AutoSize
    }

    Write-Section "3. Running Builds / Executors"

    $computer = Invoke-RestMethod `
        -Uri "$JenkinsUrl/computer/api/json?tree=computer[displayName,offline,idle,executors[currentExecutable[url,number]]]" `
        -Headers $Headers

    foreach ($node in $computer.computer) {
        Write-Host ""
        Write-Host "Node    : $($node.displayName)"
        Write-Host "Offline : $($node.offline)"
        Write-Host "Idle    : $($node.idle)"

        if ($node.executors) {
            foreach ($executor in $node.executors) {
                if ($executor.currentExecutable) {
                    Write-Host "Running Build #$($executor.currentExecutable.number): $($executor.currentExecutable.url)"
                }
            }
        }
    }

    if ([string]::IsNullOrWhiteSpace($JobName)) {
        Write-Section "4. Job-Specific Inspection"
        Write-Host "JobName is blank. Skipping job-specific inspection."
        Write-Host "Set `$JobName at the top of this script and run again to inspect one pipeline."
    }
    else {
        $EncodedJobName = [uri]::EscapeDataString($JobName)

        Write-Section "4. Job Status: $JobName"

        $job = Invoke-RestMethod `
            -Uri "$JenkinsUrl/job/$EncodedJobName/api/json?tree=name,url,color,buildable,lastBuild[number,result,timestamp,url],lastCompletedBuild[number,result,url]" `
            -Headers $Headers

        $job | ConvertTo-Json -Depth 6

        Write-Section "5. Poll SCM Configuration"

        $config = Invoke-WebRequest `
            -Uri "$JenkinsUrl/job/$EncodedJobName/config.xml" `
            -Headers $Headers

        [xml]$xml = $config.Content

        $scmTrigger = $xml.project.triggers.'hudson.triggers.SCMTrigger'

        if (-not $scmTrigger) {
            # Pipeline jobs may use a different root element.
            $scmTrigger = $xml.'flow-definition'.triggers.'hudson.triggers.SCMTrigger'
        }

        if ($scmTrigger) {
            Write-Host "[PASS] Poll SCM is configured."
            Write-Host "Schedule: $($scmTrigger.spec)"
        }
        else {
            Write-Warning "Poll SCM is NOT configured for this job."
        }

        Write-Section "6. Raw Trigger Snippet"

        $matches = Select-String `
            -InputObject $config.Content `
            -Pattern "SCMTrigger|pollSCM|<spec>" `
            -AllMatches

        if ($matches) {
            $matches | ForEach-Object { $_.Line }
        }
        else {
            Write-Host "No SCM polling trigger text found in config.xml."
        }
    }

    Write-Section "DONE"
    Write-Host "Jenkins inspection completed successfully."
}
catch {
    Write-Host ""
    Write-Host "[FAIL] Jenkins inspection failed." -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}
