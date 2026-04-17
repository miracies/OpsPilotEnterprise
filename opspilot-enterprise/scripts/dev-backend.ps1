# OpsPilot Enterprise - Start all backend services for local development
# Run from the repository root: .\scripts\dev-backend.ps1

$ErrorActionPreference = "Continue"
$root = Split-Path -Parent $PSScriptRoot

Write-Host "=== Installing shared schema ===" -ForegroundColor Cyan
pip install -e "$root\packages\shared-schema" 2>&1 | Out-Null

$services = @(
    @{ Name = "tool-gateway";           Port = 8020; Path = "$root\services\tool-gateway" },
    @{ Name = "vmware-skill-gateway";   Port = 8030; Path = "$root\services\vmware-skill-gateway" },
    @{ Name = "change-impact-service";  Port = 8040; Path = "$root\services\change-impact-service" },
    @{ Name = "evidence-aggregator";    Port = 8050; Path = "$root\services\evidence-aggregator" },
    @{ Name = "topology-service";      Port = 8090; Path = "$root\services\topology-service" },
    @{ Name = "event-ingestion-service"; Port = 8060; Path = "$root\services\event-ingestion-service" },
    @{ Name = "langgraph-orchestrator"; Port = 8010; Path = "$root\services\langgraph-orchestrator" },
    @{ Name = "api-bff";               Port = 8000; Path = "$root\apps\api-bff" }
)

$jobs = @()
foreach ($svc in $services) {
    Write-Host "Starting $($svc.Name) on port $($svc.Port)..." -ForegroundColor Green
    pip install -e $svc.Path 2>&1 | Out-Null
    $job = Start-Job -ScriptBlock {
        param($p, $port)
        Set-Location $p
        uvicorn app.main:app --host 0.0.0.0 --port $port --reload
    } -ArgumentList $svc.Path, $svc.Port
    $jobs += $job
}

Write-Host "`n=== All services started ===" -ForegroundColor Cyan
Write-Host "  API BFF:           http://localhost:8000"
Write-Host "  Orchestrator:      http://localhost:8010"
Write-Host "  Tool Gateway:      http://localhost:8020"
Write-Host "  VMware Gateway:    http://localhost:8030"
Write-Host "  Change Impact:     http://localhost:8040"
Write-Host "  Evidence Agg:      http://localhost:8050"
Write-Host "  Event Ingestion:   http://localhost:8060"
Write-Host "`nPress Ctrl+C to stop all services.`n"

try {
    $jobs | Wait-Job
} finally {
    $jobs | Stop-Job -PassThru | Remove-Job
}
