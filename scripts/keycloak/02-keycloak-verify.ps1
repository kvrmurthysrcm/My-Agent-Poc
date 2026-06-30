Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$KeycloakUrl = "http://localhost:8080"
$Realm = "rag-auth-gateway"
$ClientId = "fastapi-auth-gateway"
$ClientSecret = "fastapi-auth-gateway-secret"
$ExpectedAccessTokenLifespanSeconds = 604800

$IssuerUrl = "$KeycloakUrl/realms/$Realm"
$DiscoveryUrl = "$IssuerUrl/.well-known/openid-configuration"
$JwksUrl = "$IssuerUrl/protocol/openid-connect/certs"
$TokenUrl = "$IssuerUrl/protocol/openid-connect/token"

$Users = @(
    @{ Username = "raguser"; Password = "raguser123"; ExpectedRoles = @("rag_user", "rag_search_user") },
    @{ Username = "ragadmin"; Password = "ragadmin123"; ExpectedRoles = @("rag_admin", "rag_user", "rag_search_user", "rag_ingest_user", "graph_rag_user", "system_admin") },
    @{ Username = "searchuser"; Password = "searchuser123"; ExpectedRoles = @("rag_search_user") }
)

function Assert-HttpGetJson {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Name,

        [Parameter(Mandatory = $true)]
        [string] $Url
    )

    Write-Host "Checking $Name..."
    try {
        $response = Invoke-RestMethod -Method Get -Uri $Url
        Write-Host "  OK: $Url"
        return $response
    }
    catch {
        throw "Failed to call $Name at $Url. $($_.Exception.Message)"
    }
}

function Request-Token {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Username,

        [Parameter(Mandatory = $true)]
        [string] $Password
    )

    $body = @{
        grant_type = "password"
        client_id = $ClientId
        client_secret = $ClientSecret
        username = $Username
        password = $Password
        scope = "openid profile email"
    }

    try {
        return Invoke-RestMethod -Method Post -Uri $TokenUrl -Body $body -ContentType "application/x-www-form-urlencoded"
    }
    catch {
        $errorDetail = $_.Exception.Message
        if ($_.Exception.Response -and $_.Exception.Response.GetResponseStream()) {
            $reader = New-Object System.IO.StreamReader($_.Exception.Response.GetResponseStream())
            $responseBody = $reader.ReadToEnd()
            if (-not [string]::IsNullOrWhiteSpace($responseBody)) {
                $errorDetail = "$errorDetail Response: $responseBody"
            }
        }

        throw "Token request failed for user '$Username'. $errorDetail"
    }
}

function Get-TokenPreview {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Token
    )

    if ($Token.Length -le 30) {
        return $Token
    }

    return $Token.Substring(0, 30)
}

function ConvertFrom-Base64UrlJson {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Value
    )

    $base64 = $Value.Replace("-", "+").Replace("_", "/")
    switch ($base64.Length % 4) {
        2 { $base64 += "==" }
        3 { $base64 += "=" }
        0 { }
        default { throw "Invalid base64url token segment length." }
    }

    $json = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String($base64))
    return $json | ConvertFrom-Json
}

function Assert-TokenRoles {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Username,

        [Parameter(Mandatory = $true)]
        [string] $Token,

        [Parameter(Mandatory = $true)]
        [string[]] $ExpectedRoles
    )

    $parts = $Token.Split(".")
    if ($parts.Count -lt 2) {
        throw "Access token for '$Username' is not a JWT."
    }

    $payload = ConvertFrom-Base64UrlJson -Value $parts[1]
    if ($null -eq $payload.realm_access -or $null -eq $payload.realm_access.roles) {
        throw "Access token for '$Username' does not contain realm_access.roles."
    }

    foreach ($expectedRole in $ExpectedRoles) {
        if ($payload.realm_access.roles -notcontains $expectedRole) {
            throw "Access token for '$Username' is missing expected role '$expectedRole'."
        }
    }
}

function Assert-TokenLifespan {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Username,

        [Parameter(Mandatory = $true)]
        [string] $Token
    )

    $payload = ConvertFrom-Base64UrlJson -Value ($Token.Split(".")[1])
    if ($null -eq $payload.exp -or $null -eq $payload.iat) {
        throw "Access token for '$Username' does not contain exp and iat claims."
    }

    $lifespanSeconds = [int64]$payload.exp - [int64]$payload.iat
    if ([Math]::Abs($lifespanSeconds - $ExpectedAccessTokenLifespanSeconds) -gt 5) {
        throw "Access token for '$Username' has lifespan $lifespanSeconds seconds; expected about $ExpectedAccessTokenLifespanSeconds seconds."
    }
}

Assert-HttpGetJson -Name "discovery document" -Url $DiscoveryUrl | Out-Null
$jwks = Assert-HttpGetJson -Name "JWKS document" -Url $JwksUrl

if ($null -eq $jwks.keys -or $jwks.keys.Count -eq 0) {
    throw "JWKS document was returned, but no signing keys were found."
}

Write-Host ""
Write-Host "Requesting user tokens..."

foreach ($user in $Users) {
    $tokenResponse = Request-Token -Username $user.Username -Password $user.Password

    if ([string]::IsNullOrWhiteSpace($tokenResponse.access_token)) {
        throw "No access_token received for user '$($user.Username)'."
    }

    $preview = Get-TokenPreview -Token $tokenResponse.access_token
    Assert-TokenRoles -Username $user.Username -Token $tokenResponse.access_token -ExpectedRoles $user.ExpectedRoles
    Assert-TokenLifespan -Username $user.Username -Token $tokenResponse.access_token
    Write-Host "  OK: $($user.Username) received access_token with expected realm roles and 7-day lifespan: $preview..."
}

Write-Host ""
Write-Host "Keycloak verification complete."
Write-Host "Issuer URL: $IssuerUrl"
Write-Host "Token URL:  $TokenUrl"
Write-Host "JWKS URL:   $JwksUrl"
Write-Host "JWT lifespan: $ExpectedAccessTokenLifespanSeconds seconds (7 days, local POC only)"
