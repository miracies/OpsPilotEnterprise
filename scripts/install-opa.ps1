param(
    [string]$Version = "v1.15.2",
    [string]$Destination = "",
    [switch]$Force
)

$ErrorActionPreference = "Stop"

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
if (-not $Destination) {
    $Destination = Join-Path $projectRoot "tools\opa.exe"
}

$destinationDir = Split-Path $Destination -Parent
New-Item -ItemType Directory -Force -Path $destinationDir | Out-Null

if ((Test-Path $Destination) -and -not $Force) {
    Write-Host "OPA already exists: $Destination"
    & $Destination version
    exit 0
}

$url = "https://github.com/open-policy-agent/opa/releases/download/$Version/opa_windows_amd64.exe"
$tempPath = "$Destination.download"

Write-Host "Downloading OPA $Version from $url"
Invoke-WebRequest -Uri $url -OutFile $tempPath
Move-Item -Force -Path $tempPath -Destination $Destination

Write-Host "Installed OPA to $Destination"
& $Destination version
