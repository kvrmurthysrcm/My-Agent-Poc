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
$ClientId = "fastapi-auth-gateway"
$ClientSecret = "fastapi-auth-gateway-secret"
$AdminClientId = "secure-gateway-admin"
$AdminClientSecret = "secure-gateway-admin-secret"
$WrapperUrl = "http://localhost:8010"
$SevenDaysInSeconds = 604800

$Roles = @(
    "rag_user",
    "rag_admin",
    "rag_search_user",
    "rag_ingest_user",
    "graph_rag_user",
    "system_admin"
)

$Users = @(
    @{
        Username = "raguser"
        Password = "raguser123"
        Email = "raguser@example.local"
        FirstName = "RAG"
        LastName = "User"
        Roles = @("rag_user", "rag_search_user")
    },
    @{
        Username = "ragadmin"
        Password = "ragadmin123"
        Email = "ragadmin@example.local"
        FirstName = "RAG"
        LastName = "Admin"
        Roles = @("rag_admin", "rag_user", "rag_search_user", "rag_ingest_user", "graph_rag_user", "system_admin")
    },
    @{
        Username = "searchuser"
        Password = "searchuser123"
        Email = "searchuser@example.local"
        FirstName = "Search"
        LastName = "User"
        Roles = @("rag_search_user")
    }
)

function Invoke-KeycloakAdmin {
    param(
        [Parameter(Mandatory = $true)]
        [string[]] $Arguments,

        [switch] $AllowFailure
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
    $output = @()
    $stdout = Get-Content -Raw -LiteralPath $tempOut
    $stderr = Get-Content -Raw -LiteralPath $tempErr
    Remove-Item -LiteralPath $tempOut, $tempErr -Force

    if (-not [string]::IsNullOrWhiteSpace($stdout)) {
        $output += $stdout.Trim()
    }
    if (-not [string]::IsNullOrWhiteSpace($stderr)) {
        $output += $stderr.Trim()
    }

    if ($exitCode -ne 0 -and -not $AllowFailure) {
        throw "kcadm failed with exit code $exitCode. Command: $($Arguments -join ' '). Output: $output"
    }

    return [PSCustomObject]@{
        ExitCode = $exitCode
        Output = $output
        StdOut = $stdout
        StdErr = $stderr
    }
}

function Get-KeycloakIdFromOutput {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Output
    )

    if ($Output -match "Created new .+ with id '([^']+)'" -or $Output -match "id=([A-Za-z0-9._:-]+)") {
        return $Matches[1]
    }

    return $null
}

function Ensure-Realm {
    $result = Invoke-KeycloakAdmin -Arguments @("get", "realms/$Realm") -AllowFailure
    if ($result.ExitCode -eq 0) {
        Write-Host "Realm already exists: $Realm"
        return
    }

    Write-Host "Creating realm: $Realm"
    Invoke-KeycloakAdmin -Arguments @(
        "create", "realms",
        "-s", "realm=$Realm",
        "-s", "enabled=true",
        "-s", "displayName=RAG Auth Gateway"
    ) | Out-Null
}

function Ensure-LocalTokenLifespans {
    Write-Host "Configuring local POC token/session lifespans to 7 days..."
    Invoke-KeycloakAdmin -Arguments @(
        "update", "realms/$Realm",
        "-s", "accessTokenLifespan=$SevenDaysInSeconds",
        "-s", "ssoSessionIdleTimeout=$SevenDaysInSeconds",
        "-s", "ssoSessionMaxLifespan=$SevenDaysInSeconds",
        "-s", "clientSessionIdleTimeout=$SevenDaysInSeconds",
        "-s", "clientSessionMaxLifespan=$SevenDaysInSeconds"
    ) | Out-Null
}

function Ensure-RealmRole {
    param(
        [Parameter(Mandatory = $true)]
        [string] $RoleName
    )

    $result = Invoke-KeycloakAdmin -Arguments @("get", "roles/$RoleName", "-r", $Realm) -AllowFailure
    if ($result.ExitCode -eq 0) {
        Write-Host "Role already exists: $RoleName"
        return
    }

    Write-Host "Creating role: $RoleName"
    Invoke-KeycloakAdmin -Arguments @("create", "roles", "-r", $Realm, "-s", "name=$RoleName") | Out-Null
}

function Get-ClientUuidByClientId {
    param(
        [Parameter(Mandatory = $true)]
        [string] $LookupClientId
    )

    $clientList = Invoke-KeycloakAdmin -Arguments @("get", "clients", "-r", $Realm, "-q", "clientId=$LookupClientId")
    $clients = $clientList.StdOut | ConvertFrom-Json
    if ($clients.Count -eq 0) {
        return $null
    }

    return $clients[0].id
}

function Get-ClientUuid {
    return Get-ClientUuidByClientId -LookupClientId $ClientId
}

function Ensure-Client {
    $clientUuid = Get-ClientUuid

    if ([string]::IsNullOrWhiteSpace($clientUuid)) {
        Write-Host "Creating client: $ClientId"
        $result = Invoke-KeycloakAdmin -Arguments @(
            "create", "clients",
            "-r", $Realm,
            "-s", "clientId=$ClientId",
            "-s", "enabled=true",
            "-s", "protocol=openid-connect",
            "-s", "publicClient=false",
            "-s", "standardFlowEnabled=true",
            "-s", "directAccessGrantsEnabled=true",
            "-s", "serviceAccountsEnabled=false",
            "-s", "secret=$ClientSecret",
            "-s", "redirectUris=[`"$WrapperUrl/*`",`"$WrapperUrl/docs/oauth2-redirect`"]",
            "-s", "webOrigins=[`"$WrapperUrl`",`"http://localhost:3000`",`"http://localhost:4200`"]"
        )

        $clientUuid = Get-KeycloakIdFromOutput -Output ($result.Output -join "`n")
        if ([string]::IsNullOrWhiteSpace($clientUuid)) {
            $clientUuid = Get-ClientUuid
        }
    }
    else {
        Write-Host "Updating client: $ClientId"
        Invoke-KeycloakAdmin -Arguments @(
            "update", "clients/$clientUuid",
            "-r", $Realm,
            "-s", "enabled=true",
            "-s", "protocol=openid-connect",
            "-s", "publicClient=false",
            "-s", "standardFlowEnabled=true",
            "-s", "directAccessGrantsEnabled=true",
            "-s", "serviceAccountsEnabled=false",
            "-s", "secret=$ClientSecret",
            "-s", "redirectUris=[`"$WrapperUrl/*`",`"$WrapperUrl/docs/oauth2-redirect`"]",
            "-s", "webOrigins=[`"$WrapperUrl`",`"http://localhost:3000`",`"http://localhost:4200`"]"
        ) | Out-Null
    }

    if ([string]::IsNullOrWhiteSpace($clientUuid)) {
        throw "Unable to resolve client UUID for $ClientId"
    }

    Write-Host "Client secret configured for: $ClientId"
}

function Ensure-AdminClient {
    $clientUuid = Get-ClientUuidByClientId -LookupClientId $AdminClientId

    if ([string]::IsNullOrWhiteSpace($clientUuid)) {
        Write-Host "Creating admin service-account client: $AdminClientId"
        $result = Invoke-KeycloakAdmin -Arguments @(
            "create", "clients",
            "-r", $Realm,
            "-s", "clientId=$AdminClientId",
            "-s", "enabled=true",
            "-s", "protocol=openid-connect",
            "-s", "publicClient=false",
            "-s", "standardFlowEnabled=false",
            "-s", "directAccessGrantsEnabled=false",
            "-s", "serviceAccountsEnabled=true",
            "-s", "authorizationServicesEnabled=false",
            "-s", "secret=$AdminClientSecret"
        )

        $clientUuid = Get-KeycloakIdFromOutput -Output ($result.Output -join "`n")
        if ([string]::IsNullOrWhiteSpace($clientUuid)) {
            $clientUuid = Get-ClientUuidByClientId -LookupClientId $AdminClientId
        }
    }
    else {
        Write-Host "Updating admin service-account client: $AdminClientId"
        Invoke-KeycloakAdmin -Arguments @(
            "update", "clients/$clientUuid",
            "-r", $Realm,
            "-s", "enabled=true",
            "-s", "protocol=openid-connect",
            "-s", "publicClient=false",
            "-s", "standardFlowEnabled=false",
            "-s", "directAccessGrantsEnabled=false",
            "-s", "serviceAccountsEnabled=true",
            "-s", "authorizationServicesEnabled=false",
            "-s", "secret=$AdminClientSecret"
        ) | Out-Null
    }

    if ([string]::IsNullOrWhiteSpace($clientUuid)) {
        throw "Unable to resolve client UUID for $AdminClientId"
    }

    Ensure-AdminClientRoleMappings -AdminClientUuid $clientUuid
    Write-Host "Admin client secret configured for: $AdminClientId"
}

function Ensure-AdminClientRoleMappings {
    param(
        [Parameter(Mandatory = $true)]
        [string] $AdminClientUuid
    )

    $realmManagementClientUuid = Get-ClientUuidByClientId -LookupClientId "realm-management"
    if ([string]::IsNullOrWhiteSpace($realmManagementClientUuid)) {
        throw "Unable to resolve realm-management client UUID"
    }

    $serviceAccountUser = Invoke-KeycloakAdmin -Arguments @("get", "clients/$AdminClientUuid/service-account-user", "-r", $Realm)
    $serviceAccount = $serviceAccountUser.StdOut | ConvertFrom-Json
    $serviceAccountUserId = $serviceAccount.id
    if ([string]::IsNullOrWhiteSpace($serviceAccountUserId)) {
        throw "Unable to resolve service account user for $AdminClientId"
    }

    $managementRoles = @(
        "manage-users",
        "view-users",
        "query-users",
        "view-realm"
    )

    foreach ($roleName in $managementRoles) {
        Write-Host "Assigning realm-management role '$roleName' to service account: $AdminClientId"
        Invoke-KeycloakAdmin -Arguments @(
            "add-roles",
            "-r", $Realm,
            "--uid", $serviceAccountUserId,
            "--cclientid", "realm-management",
            "--rolename", $roleName
        ) | Out-Null
    }
}

function Get-UserId {
    param(
        [Parameter(Mandatory = $true)]
        [string] $Username
    )

    $userList = Invoke-KeycloakAdmin -Arguments @("get", "users", "-r", $Realm, "-q", "username=$Username")
    $users = $userList.StdOut | ConvertFrom-Json
    if ($users.Count -eq 0) {
        return $null
    }

    return $users[0].id
}

function Ensure-User {
    param(
        [Parameter(Mandatory = $true)]
        [hashtable] $User
    )

    $username = $User.Username
    $userId = Get-UserId -Username $username

    if ([string]::IsNullOrWhiteSpace($userId)) {
        Write-Host "Creating user: $username"
        $result = Invoke-KeycloakAdmin -Arguments @(
            "create", "users",
            "-r", $Realm,
            "-s", "username=$username",
            "-s", "email=$($User.Email)",
            "-s", "firstName=$($User.FirstName)",
            "-s", "lastName=$($User.LastName)",
            "-s", "enabled=true",
            "-s", "emailVerified=true",
            "-s", "requiredActions=[]"
        )

        $userId = Get-KeycloakIdFromOutput -Output ($result.Output -join "`n")
        if ([string]::IsNullOrWhiteSpace($userId)) {
            $userId = Get-UserId -Username $username
        }
    }
    else {
        Write-Host "Updating user: $username"
        Invoke-KeycloakAdmin -Arguments @(
            "update", "users/$userId",
            "-r", $Realm,
            "-s", "email=$($User.Email)",
            "-s", "firstName=$($User.FirstName)",
            "-s", "lastName=$($User.LastName)",
            "-s", "enabled=true",
            "-s", "emailVerified=true",
            "-s", "requiredActions=[]"
        ) | Out-Null
    }

    if ([string]::IsNullOrWhiteSpace($userId)) {
        throw "Unable to resolve user ID for $username"
    }

    Write-Host "Setting password for user: $username"
    Invoke-KeycloakAdmin -Arguments @(
        "set-password",
        "-r", $Realm,
        "--username", $username,
        "--new-password", $User.Password
    ) | Out-Null

    foreach ($roleName in $User.Roles) {
        Write-Host "Assigning role '$roleName' to user: $username"
        Invoke-KeycloakAdmin -Arguments @(
            "add-roles",
            "-r", $Realm,
            "--uusername", $username,
            "--rolename", $roleName
        ) | Out-Null
    }
}

Write-Host "Using transient Keycloak admin CLI authentication..."

Ensure-Realm
Ensure-LocalTokenLifespans

foreach ($role in $Roles) {
    Ensure-RealmRole -RoleName $role
}

Ensure-Client
Ensure-AdminClient

foreach ($user in $Users) {
    Ensure-User -User $user
}

$IssuerUrl = "$KeycloakUrl/realms/$Realm"
$TokenUrl = "$IssuerUrl/protocol/openid-connect/token"
$JwksUrl = "$IssuerUrl/protocol/openid-connect/certs"
$DiscoveryUrl = "$IssuerUrl/.well-known/openid-configuration"

Write-Host ""
Write-Host "Keycloak setup complete."
Write-Host "Realm:        $Realm"
Write-Host "Client ID:    $ClientId"
Write-Host "Admin Client: $AdminClientId"
Write-Host "Issuer URL:   $IssuerUrl"
Write-Host "Discovery:    $DiscoveryUrl"
Write-Host "Token URL:    $TokenUrl"
Write-Host "JWKS URL:     $JwksUrl"
Write-Host "JWT lifespan: $SevenDaysInSeconds seconds (7 days, local POC only)"
Write-Host ""
Write-Host "Sample users:"
Write-Host "  raguser / raguser123"
Write-Host "  ragadmin / ragadmin123"
Write-Host "  searchuser / searchuser123"
