# scripts/run.ps1 - Start VoltAgent FastAPI service and frontend
[CmdletBinding()]
param(
    [string]$BindHost = "127.0.0.1",
    [int]$Port = 8000
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment not found at $VenvPython. Please run .\scripts\setup.ps1 first."
    exit 1
}

$EnvFile = Join-Path $RepoRoot ".env"
if (-not (Test-Path $EnvFile)) {
    Write-Warning "Warning: .env file missing. Run .\scripts\setup.ps1 to initialize it."
}

Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host " VoltAgent -- Field Copilot for EV Charger Technicians" -ForegroundColor Cyan
Write-Host "===========================================================" -ForegroundColor Cyan
Write-Host " Serving UI and API at: http://${BindHost}:${Port}/" -ForegroundColor Green
Write-Host " Browser mic: Chrome / Edge allow microphone on http://localhost" -ForegroundColor Yellow
Write-Host " Health check: http://${BindHost}:${Port}/health"
Write-Host " Readiness probe: http://${BindHost}:${Port}/ready"
Write-Host " Press CTRL+C to stop the server.`n"

# Run Uvicorn directly from virtual environment with working directory at RepoRoot
Push-Location $RepoRoot
try {
    & $VenvPython -m uvicorn voltagent.api.main:app --host $BindHost --port $Port
} finally {
    Pop-Location
}
