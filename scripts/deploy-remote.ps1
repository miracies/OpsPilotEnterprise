param(
    [Parameter(Mandatory = $true)]
    [string]$RemoteHost,
    [string]$User = "root",
    [int]$Port = 22,
    [string]$RemoteBaseDir = "/opt/opspilot",
    [string]$ProjectDirName = "opspilot-enterprise",
    [string]$KubeconfigPath = "",
    [switch]$DisableK8sMonitoring,
    [switch]$SkipBootstrap,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Command,
        [string]$WorkingDirectory = ""
    )

    if ($WorkingDirectory) {
        Push-Location $WorkingDirectory
    }
    try {
        Write-Host ">> $Command"
        Invoke-Expression $Command
        if ($LASTEXITCODE -ne 0) {
            throw "Command failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        if ($WorkingDirectory) {
            Pop-Location
        }
    }
}

$projectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$bootstrapScript = Join-Path $projectRoot "deploy\scripts\bootstrap-remote.sh"
$tmpDir = Join-Path $projectRoot "tmp\deploy-remote"
$archiveName = "$ProjectDirName-deploy.tgz"
$archivePath = Join-Path $tmpDir $archiveName
$target = "$User@$RemoteHost"
$remoteProjectDir = "$RemoteBaseDir/$ProjectDirName"
$remoteArchivePath = "/tmp/$archiveName"
$remoteBootstrapPath = "/tmp/bootstrap-opspilot.sh"
$sshBase = "ssh -p $Port -o BatchMode=yes -o ConnectTimeout=20 $target"
$scpBase = "scp -P $Port -O"

New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null

if (-not (Test-Path $projectRoot)) {
    throw "Project root not found: $projectRoot"
}
if (-not (Test-Path $bootstrapScript)) {
    throw "Bootstrap script not found: $bootstrapScript"
}

$envPath = Join-Path $projectRoot ".env"
if (-not (Test-Path $envPath)) {
    throw ".env not found: $envPath"
}

$excludeArgs = @(
    "--exclude=.git",
    "--exclude=node_modules",
    "--exclude=apps/web/.next",
    "--exclude=apps/web/node_modules",
    "--exclude=tmp",
    "--exclude=tmp-*",
    "--exclude=**/__pycache__",
    "--exclude=**/*.pyc"
) -join " "

if (Test-Path $archivePath) {
    Remove-Item $archivePath -Force
}

Invoke-Checked -Command "tar -czf `"$archivePath`" $excludeArgs -C `"$projectRoot`" ."
Invoke-Checked -Command "$sshBase `"mkdir -p $RemoteBaseDir /tmp`""

if (-not $SkipBootstrap) {
    Invoke-Checked -Command "$scpBase `"$bootstrapScript`" ${target}:$remoteBootstrapPath"
    Invoke-Checked -Command "$sshBase `"chmod +x $remoteBootstrapPath && bash $remoteBootstrapPath`""
}

Invoke-Checked -Command "$scpBase `"$archivePath`" ${target}:$remoteArchivePath"

if ($KubeconfigPath) {
    if (-not (Test-Path $KubeconfigPath)) {
        throw "Kubeconfig not found: $KubeconfigPath"
    }
    Invoke-Checked -Command "$sshBase `"mkdir -p /root/.kube`""
    Invoke-Checked -Command "$scpBase `"$KubeconfigPath`" ${target}:/root/.kube/config"
    Invoke-Checked -Command "$sshBase `"chmod 600 /root/.kube/config`""
}

$remotePrepare = @"
set -euo pipefail
mkdir -p '$RemoteBaseDir'
rm -rf '$remoteProjectDir'
mkdir -p '$remoteProjectDir'
tar -xzf '$remoteArchivePath' -C '$remoteProjectDir'
python3 - <<'PY'
from pathlib import Path
root = Path('$remoteProjectDir')
patterns = ('Dockerfile', 'docker-compose.yml', '.env', '.sh', '.ps1')
for path in root.rglob('*'):
    if not path.is_file():
        continue
    if path.name in patterns or path.suffix in {'.sh', '.ps1'}:
        data = path.read_bytes()
        if data.startswith(b'\xef\xbb\xbf'):
            path.write_bytes(data[3:])
PY
"@
Invoke-Checked -Command "$sshBase `"$remotePrepare`""

if ($DisableK8sMonitoring) {
    $remoteEnvPatch = @"
python3 - <<'PY'
from pathlib import Path
path = Path('$remoteProjectDir/.env')
lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
key = 'K8S_WORKLOAD_INTERVAL_SECONDS'
updated = False
for idx, line in enumerate(lines):
    if line.startswith(key + '='):
        lines[idx] = key + '=0'
        updated = True
if not updated:
    lines.append(key + '=0')
path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
PY
"@
    Invoke-Checked -Command "$sshBase `"$remoteEnvPatch`""
}
elseif ($KubeconfigPath) {
    $remoteEnvPatch = @"
python3 - <<'PY'
from pathlib import Path
path = Path('$remoteProjectDir/.env')
lines = path.read_text(encoding='utf-8', errors='replace').splitlines()
key = 'K8S_KUBECONFIG_PATH'
value = '/root/.kube/config'
updated = False
for idx, line in enumerate(lines):
    if line.startswith(key + '='):
        lines[idx] = key + '=' + value
        updated = True
if not updated:
    lines.append(key + '=' + value)
path.write_text('\n'.join(lines) + '\n', encoding='utf-8')
PY
"@
    Invoke-Checked -Command "$sshBase `"$remoteEnvPatch`""
}

if (-not $SkipBuild) {
$remoteDeploy = @"
set -euo pipefail
cd '$remoteProjectDir/deploy/docker'
docker compose up -d --build
bash '$remoteProjectDir/deploy/scripts/configure-opensearch-anonymous.sh'
docker compose up -d opensearch-dashboards
docker compose ps
"@
    Invoke-Checked -Command "$sshBase `"$remoteDeploy`""
}

$remoteChecks = @"
set -euo pipefail
cd '$remoteProjectDir/deploy/docker'
echo '=== docker compose ps ==='
docker compose ps
echo '=== web ==='
curl -sS -I http://127.0.0.1:3000 | head -n 1
echo '=== api-bff ==='
curl -sS -o /tmp/api-bff-health.out -w '%{http_code}\n' http://127.0.0.1:8000/api/v1/chat/sessions
echo '=== event-ingestion ==='
curl -sS -o /tmp/event-ingestion-health.out -w '%{http_code}\n' http://127.0.0.1:8060/api/v1/monitoring/status
"@
Invoke-Checked -Command "$sshBase `"$remoteChecks`""

Write-Host ""
Write-Host "Deployment completed."
Write-Host "Web: http://${RemoteHost}:3000"
Write-Host "API: http://${RemoteHost}:8000"
