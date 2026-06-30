Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$Port = 8010
$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..")
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    $Python = "python"
}

Write-Host "Starting secure-api-gateway on http://localhost:$Port"
Push-Location $PSScriptRoot
try {
    & $Python -m uvicorn app.main:app --reload --port $Port
}
finally {
    Pop-Location
}
