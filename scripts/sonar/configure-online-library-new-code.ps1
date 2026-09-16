param(
    [string]$SonarUrl = "http://localhost:9000",
    [string]$ProjectKey = "my-agent-poc-online-library",
    [ValidateRange(1, 90)]
    [int]$Days = 30
)

$ErrorActionPreference = "Stop"

if ([string]::IsNullOrWhiteSpace($env:SONAR_ADMIN_TOKEN)) {
    throw "Set SONAR_ADMIN_TOKEN to a SonarQube user token with Administer Project permission. Do not put the token in this script."
}

$headers = @{ Authorization = "Bearer $($env:SONAR_ADMIN_TOKEN)" }
$body = @{
    project = $ProjectKey
    type = "NUMBER_OF_DAYS"
    value = $Days
}

Invoke-RestMethod `
    -Method Post `
    -Uri "$($SonarUrl.TrimEnd('/'))/api/new_code_periods/set" `
    -Headers $headers `
    -ContentType "application/x-www-form-urlencoded" `
    -Body $body | Out-Null

Write-Host "Configured project '$ProjectKey' to treat the last $Days day(s) as new code."
