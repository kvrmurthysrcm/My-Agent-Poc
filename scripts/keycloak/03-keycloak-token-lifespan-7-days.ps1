Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
if (Test-Path Variable:\PSNativeCommandUseErrorActionPreference) {
    $PSNativeCommandUseErrorActionPreference = $false
}

$ContainerName = "local-keycloak"
$KeycloakUrl = "http://localhost:8080"
$AdminUser = "admin"
$AdminPassword = "admin123"
$Realm = "rag-auth-gateway"
$SevenDaysInSeconds = 604800

function Invoke-KeycloakAdmin {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments
    )

    function ConvertTo-ProcessArgument {
        param(
            [Parameter(Mandatory = $true)]
            [string] $Value
        )

        if ($Value -notmatch '[\s"]') {
            return $Value
        }

        return '"' + ($Value -replace '"', '\"') + '"'
    }

    $credentialArguments = @("--no-config", "--server", $KeycloakUrl, "--realm", "master", "--user", $AdminUser, "--password", $AdminPassword)
    $tempOut = [System.IO.Path]::GetTempFileName()
    $tempErr = [System.IO.Path]::GetTempFileName()
    $allArguments = @("exec", $ContainerName, "/opt/keycloak/bin/kcadm.sh") + $Arguments + $credentialArguments
    $dockerArguments = ($allArguments | ForEach-Object { ConvertTo-ProcessArgument -Value $_ }) -join " "

    $process = Start-Process -FilePath "docker" -ArgumentList $dockerArguments -NoNewWindow -Wait -PassThru -RedirectStandardOutput $tempOut -RedirectStandardError $tempErr

    $exitCode = $process.ExitCode
    $stdout = Get-Content -Raw -LiteralPath $tempOut
    $stderr = Get-Content -Raw -LiteralPath $tempErr
    Remove-Item -LiteralPath $tempOut, $tempErr -Force

    if ($exitCode -ne 0) {
        throw "kcadm failed with exit code $exitCode. Command: $($Arguments -join ' '). Output: $stdout $stderr"
    }

    return [PSCustomObject]@{
        StdOut = $stdout
        StdErr = $stderr
    }
}

Write-Host "Configuring Keycloak token/session lifespans for local POC testing..."
Write-Host "Realm: $Realm"
Write-Host "Access token lifespan: $SevenDaysInSeconds seconds (7 days)"

Invoke-KeycloakAdmin -Arguments @(
    "update", "realms/$Realm",
    "-s", "accessTokenLifespan=$SevenDaysInSeconds",
    "-s", "ssoSessionIdleTimeout=$SevenDaysInSeconds",
    "-s", "ssoSessionMaxLifespan=$SevenDaysInSeconds",
    "-s", "clientSessionIdleTimeout=$SevenDaysInSeconds",
    "-s", "clientSessionMaxLifespan=$SevenDaysInSeconds"
) | Out-Null

$realmJson = Invoke-KeycloakAdmin -Arguments @("get", "realms/$Realm")
$realm = $realmJson.StdOut | ConvertFrom-Json

Write-Host ""
Write-Host "Keycloak 7-day local POC token configuration applied."
Write-Host "accessTokenLifespan:       $($realm.accessTokenLifespan)"
Write-Host "ssoSessionIdleTimeout:     $($realm.ssoSessionIdleTimeout)"
Write-Host "ssoSessionMaxLifespan:     $($realm.ssoSessionMaxLifespan)"
Write-Host "clientSessionIdleTimeout:  $($realm.clientSessionIdleTimeout)"
Write-Host "clientSessionMaxLifespan:  $($realm.clientSessionMaxLifespan)"
