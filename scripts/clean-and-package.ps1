<#
.SYNOPSIS
    Removes generated build files and creates a clean source archive.

.DESCRIPTION
    This script removes common Python, Angular/Node, test, and local runtime
    artifacts from this repository. It then packages the remaining source,
    configuration, scripts, and documentation into a timestamped ZIP under
    artifacts/.

    The ZIP deliberately excludes version-control data, IDE settings, generated
    files, local runtime data, and common secret-file formats.

.EXAMPLE
    .\scripts\clean-and-package.ps1

.EXAMPLE
    # Preview every action without changing files.
    .\scripts\clean-and-package.ps1 -WhatIf

.EXAMPLE
    # Only clean generated files; do not create an archive.
    .\scripts\clean-and-package.ps1 -CleanOnly

.EXAMPLE
    # Write a specifically named archive below the repository root.
    .\scripts\clean-and-package.ps1 -OutputDirectory .\artifacts\review -ArchiveName review-copy.zip
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'Medium')]
param(
    [string]$OutputDirectory = 'artifacts',
    [string]$ArchiveName,
    [switch]$CleanOnly,
    [switch]$PackageOnly
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($CleanOnly -and $PackageOnly) {
    throw 'Use either -CleanOnly or -PackageOnly, not both.'
}

$ProjectRoot = (Get-Item -LiteralPath (Join-Path -Path $PSScriptRoot -ChildPath '..')).FullName.TrimEnd([char[]]@('\', '/'))
$ProjectRootPrefix = $ProjectRoot + [System.IO.Path]::DirectorySeparatorChar

function Get-ProjectChildPath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Path
    )

    $fullPath = [System.IO.Path]::GetFullPath($Path).TrimEnd([char[]]@('\', '/'))
    if (-not $fullPath.StartsWith($ProjectRootPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "Path must be below the project root: $Path"
    }

    return $fullPath
}

function Get-ProjectRelativePath {
    param(
        [Parameter(Mandatory = $true)]
        [string]$FullPath
    )

    return $FullPath.Substring($ProjectRoot.Length).TrimStart([char[]]@('\', '/'))
}

$OutputDirectoryFullPath = if ([System.IO.Path]::IsPathRooted($OutputDirectory)) {
    Get-ProjectChildPath -Path $OutputDirectory
}
else {
    Get-ProjectChildPath -Path (Join-Path -Path $ProjectRoot -ChildPath $OutputDirectory)
}

if ([string]::IsNullOrWhiteSpace($ArchiveName)) {
    $ArchiveName = '{0}-source-{1}Z.zip' -f (Split-Path -Leaf $ProjectRoot), (Get-Date).ToUniversalTime().ToString('yyyyMMdd-HHmmss')
}

if ([System.IO.Path]::GetFileName($ArchiveName) -ne $ArchiveName -or
    $ArchiveName.IndexOfAny([System.IO.Path]::GetInvalidFileNameChars()) -ge 0 -or
    -not $ArchiveName.EndsWith('.zip', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'ArchiveName must be a valid ZIP filename without a path.'
}

$ArchivePath = Get-ProjectChildPath -Path (Join-Path -Path $OutputDirectoryFullPath -ChildPath $ArchiveName)
$OutputDirectoryPrefix = $OutputDirectoryFullPath + [System.IO.Path]::DirectorySeparatorChar

# These are generated directories safe to remove when preparing a fresh copy.
$BuildDirectoryNames = @(
    '__pycache__', '.pytest_cache', '.mypy_cache', '.ruff_cache', '.hypothesis',
    '.tox', '.nox', '.venv', 'venv', 'node_modules', 'dist', 'build', 'coverage',
    'htmlcov', '.angular', '.next', '.nuxt', '.turbo', '.cache', '.sass-cache',
    'target', 'out', '.port-forward-logs', '.port-forward-pids'
)

$BuildFilePatterns = @('*.pyc', '*.pyo', '.coverage', 'coverage.xml', 'hs_err_pid*.log')

function Test-IsBuildDirectory {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.DirectoryInfo]$Directory
    )

    return ($Directory.Name -in $BuildDirectoryNames) -or $Directory.Name.EndsWith('.egg-info', [System.StringComparison]::OrdinalIgnoreCase)
}

function Test-IsBuildFile {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.FileInfo]$File
    )

    foreach ($pattern in $BuildFilePatterns) {
        if ($File.Name -like $pattern) {
            return $true
        }
    }

    # This repository's CI test output is generated, despite being committed today.
    return (Get-ProjectRelativePath -FullPath $File.FullName) -like 'scripts\test-output-*.txt'
}

if (-not $PackageOnly) {
    $cleanupDirectories = @(
        Get-ChildItem -LiteralPath $ProjectRoot -Directory -Recurse -Force |
            Where-Object { Test-IsBuildDirectory -Directory $_ }
    )
    $cleanupFiles = @(
        Get-ChildItem -LiteralPath $ProjectRoot -File -Recurse -Force |
            Where-Object { Test-IsBuildFile -File $_ }
    )
    $cleanupTargets = @($cleanupDirectories + $cleanupFiles | Sort-Object -Property FullName -Unique)

    if ($cleanupTargets.Count -gt 0) {
        $cleanupDescription = "Remove $($cleanupTargets.Count) generated build/runtime item(s) below $ProjectRoot"
        if ($PSCmdlet.ShouldProcess($ProjectRoot, $cleanupDescription)) {
            foreach ($target in $cleanupTargets | Sort-Object -Property FullName -Descending) {
                # Every target came from a recursive enumeration of $ProjectRoot.
                # Keep the guard so a future edit cannot make deletion escape the repo.
                $safeTarget = Get-ProjectChildPath -Path $target.FullName
                if (Test-Path -LiteralPath $safeTarget) {
                    Remove-Item -LiteralPath $safeTarget -Force -Recurse
                }
            }
            Write-Host "Removed $($cleanupTargets.Count) generated build/runtime item(s)."
        }
    }
    else {
        Write-Host 'No generated build/runtime items were found.'
    }
}

if ($CleanOnly) {
    return
}

function Test-IsExcludedFromArchive {
    param(
        [Parameter(Mandatory = $true)]
        [System.IO.FileInfo]$File
    )

    if ($File.FullName.StartsWith($OutputDirectoryPrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
        return $true
    }

    $relativePath = Get-ProjectRelativePath -FullPath $File.FullName
    $pathParts = $relativePath -split '[\\/]'

    foreach ($part in $pathParts) {
        if ($part -in @('.git', '.idea', '.vs', '.vscode') -or
            $part -in $BuildDirectoryNames -or
            $part.EndsWith('.egg-info', [System.StringComparison]::OrdinalIgnoreCase)) {
            return $true
        }
    }

    if ($relativePath -like 'modules\rag-ingest-service\storage\*') {
        return $true
    }

    if (Test-IsBuildFile -File $File) {
        return $true
    }

    # Do not accidentally share local secrets. Keep example/template files.
    if ($File.Name -eq '.env' -or
        (($File.Name -like '.env.*') -and ($File.Name -notin @('.env.example', '.env.sample', '.env.template'))) -or
        $File.Name -in @('id_rsa', 'id_ed25519') -or
        $File.Extension -in @('.pem', '.key', '.pfx', '.p12')) {
        return $true
    }

    return $false
}

if (-not $PSCmdlet.ShouldProcess($ArchivePath, 'Create clean source ZIP archive')) {
    return
}

if (-not (Test-Path -LiteralPath $OutputDirectoryFullPath)) {
    [System.IO.Directory]::CreateDirectory($OutputDirectoryFullPath) | Out-Null
}

# Windows PowerShell loads ZipFile from FileSystem, but ZipArchiveMode and
# CompressionLevel live in the base compression assembly.
Add-Type -AssemblyName System.IO.Compression
Add-Type -AssemblyName System.IO.Compression.FileSystem
$temporaryArchivePath = Join-Path -Path $OutputDirectoryFullPath -ChildPath ('.{0}.{1}.partial' -f $ArchiveName, $PID)
$archive = $null
$filesAdded = 0

try {
    $archive = [System.IO.Compression.ZipFile]::Open(
        $temporaryArchivePath,
        [System.IO.Compression.ZipArchiveMode]::Create
    )

    $packageRoot = Split-Path -Leaf $ProjectRoot
    foreach ($file in Get-ChildItem -LiteralPath $ProjectRoot -File -Recurse -Force) {
        if (Test-IsExcludedFromArchive -File $file) {
            continue
        }

        $relativePath = Get-ProjectRelativePath -FullPath $file.FullName
        $entryName = '{0}/{1}' -f $packageRoot, ($relativePath -replace '\\', '/')
        [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
            $archive,
            $file.FullName,
            $entryName,
            [System.IO.Compression.CompressionLevel]::Optimal
        ) | Out-Null
        $filesAdded++
    }
}
catch {
    if ($null -ne $archive) {
        $archive.Dispose()
        $archive = $null
    }
    if (Test-Path -LiteralPath $temporaryArchivePath) {
        Remove-Item -LiteralPath $temporaryArchivePath -Force
    }
    throw
}
finally {
    if ($null -ne $archive) {
        $archive.Dispose()
    }
}

try {
    if (Test-Path -LiteralPath $ArchivePath) {
        Remove-Item -LiteralPath $ArchivePath -Force
    }
    Move-Item -LiteralPath $temporaryArchivePath -Destination $ArchivePath -Force
}
catch {
    if (Test-Path -LiteralPath $temporaryArchivePath) {
        Remove-Item -LiteralPath $temporaryArchivePath -Force
    }
    throw
}

Write-Host "Created clean source archive: $ArchivePath"
Write-Host "Included $filesAdded file(s)."
