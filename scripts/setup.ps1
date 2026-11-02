# scripts/setup.ps1 - Environment setup for VoltAgent on Windows PowerShell
[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

Write-Host "=== [1/4] Checking Python 3.11 ===" -ForegroundColor Cyan

# Locate Python 3.11 interpreter
$PythonCandidates = @("py", "python3.11", "python")
$PythonCmd = $null

foreach ($cmd in $PythonCandidates) {
    try {
        if ($cmd -eq "py") {
            $ver = & py -3.11 --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $ver -match "Python 3\.11") {
                $PythonCmd = @("py", "-3.11")
                break
            }
        } else {
            $ver = & $cmd --version 2>&1
            if ($LASTEXITCODE -eq 0 -and $ver -match "Python 3\.11") {
                $PythonCmd = @($cmd)
                break
            }
        }
    } catch {
        # ignore and try next
    }
}

if (-not $PythonCmd) {
    Write-Error "Error: Python 3.11 is required. None of 'py -3.11', 'python3.11', or 'python' returned version 3.11.x.`nPlease install Python 3.11 from https://www.python.org/downloads/ and ensure it is registered on your PATH."
    exit 1
}

Write-Host "Found Python 3.11: $($PythonCmd -join ' ')" -ForegroundColor Green

Write-Host "`n=== [2/4] Setting up virtual environment (.venv) ===" -ForegroundColor Cyan
$VenvPath = Join-Path $RepoRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment at $VenvPath..."
    & $PythonCmd -m venv $VenvPath
} else {
    Write-Host "Virtual environment already exists at $VenvPath."
}

Write-Host "Upgrading pip..."
& $VenvPython -m pip install --upgrade pip --quiet

Write-Host "`n=== [3/4] Installing core dependencies (requirements.txt) ===" -ForegroundColor Cyan
$ReqFile = Join-Path $RepoRoot "requirements.txt"
& $VenvPython -m pip install -r $ReqFile

Write-Host "`n=== [4/4] Configuring environment (.env) ===" -ForegroundColor Cyan
$EnvFile = Join-Path $RepoRoot ".env"
$EnvExample = Join-Path $RepoRoot ".env.example"

if (-not (Test-Path $EnvFile)) {
    if (Test-Path $EnvExample) {
        Copy-Item -Path $EnvExample -Destination $EnvFile
        Write-Host "Created .env from .env.example." -ForegroundColor Green
    } else {
        New-Item -ItemType File -Path $EnvFile | Out-Null
        Write-Host "Created empty .env." -ForegroundColor Green
    }
    Write-Host "ACTION REQUIRED: Open .env in your editor and set your GEMINI_API_KEY (or OPENAI_API_KEY)." -ForegroundColor Yellow
} else {
    Write-Host ".env file already exists." -ForegroundColor Green
}

Write-Host "`n=== Setup Complete! ===" -ForegroundColor Green
Write-Host "Next steps:"
Write-Host "  1. Verify .env has GEMINI_API_KEY set."
Write-Host "  2. Run '.\scripts\ingest.ps1' to build the search index."
Write-Host "  3. Run '.\scripts\run.ps1' to start VoltAgent at http://localhost:8000"

