# scripts/ingest.ps1 - Ingest full corpus into hybrid index (BM25 + Dense Qdrant)
[CmdletBinding()]
param(
    [int]$ChunkSize = 100,
    [int]$Overlap = 20
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$VenvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $VenvPython)) {
    Write-Error "Virtual environment not found at $VenvPython. Please run .\scripts\setup.ps1 first."
    exit 1
}

Write-Host "=== VoltAgent Ingestion (Idempotent) ===" -ForegroundColor Cyan
Write-Host "Corpus sources: data/raw/real + data/raw/synthetic"
Write-Host "Chunk size: $ChunkSize tokens, Overlap: $Overlap tokens"

$IngestPy = Join-Path $RepoRoot "scripts\ingest.py"

& $VenvPython $IngestPy --source "$RepoRoot\data\raw\real" "$RepoRoot\data\raw\synthetic" --chunk-size $ChunkSize --overlap $Overlap

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nIngestion completed successfully." -ForegroundColor Green
    Write-Host "Indices cached at data/index_cache/ (bm25.pkl + dense.pt)."
} else {
    Write-Error "Ingestion failed with exit code $LASTEXITCODE."
    exit $LASTEXITCODE
}

