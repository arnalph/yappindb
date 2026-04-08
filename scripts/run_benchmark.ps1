# YappinDB Bird-SQL Benchmark Runner (PowerShell)
# 
# This script runs the Bird-SQL benchmark on YappinDB.
# It supports both native benchmark and promptfoo integration.
#
# Usage:
#   .\scripts\run_benchmark.ps1                    # Run native benchmark
#   .\scripts\run_benchmark.ps1 -Limit 50          # Run with limit
#   .\scripts\run_benchmark.ps1 -Promptfoo         # Generate promptfoo config
#   .\scripts\run_benchmark.ps1 -Download          # Download Bird dataset

param(
    [switch]$Download,
    [switch]$Promptfoo,
    [int]$Limit = 0,
    [string]$Subset = "dev",
    [string]$OutputDir = "data"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  YappinDB Bird-SQL Benchmark Runner" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Download dataset if requested
if ($Download) {
    Write-Host "[1/2] Downloading Bird-SQL dataset..." -ForegroundColor Yellow
    python scripts/download_bird.py --output $OutputDir --subset $Subset
    
    Write-Host ""
    Write-Host "Dataset downloaded successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Note: You still need to download SQLite databases from:" -ForegroundColor Yellow
    Write-Host "      https://bird-bench.github.io/" -ForegroundColor Yellow
    Write-Host ""
    exit 0
}

# Check if config.json exists
if (-not (Test-Path "config.json")) {
    Write-Host "Error: config.json not found!" -ForegroundColor Red
    exit 1
}

# Generate promptfoo config if requested
if ($Promptfoo) {
    Write-Host "[1/2] Generating promptfoo configuration..." -ForegroundColor Yellow
    python -m rag_agent.benchmark --promptfoo
    
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Error generating promptfoo config" -ForegroundColor Red
        exit 1
    }
    
    Write-Host ""
    Write-Host "Generated: promptfooconfig.yaml" -ForegroundColor Green
    Write-Host ""
    Write-Host "To run promptfoo:" -ForegroundColor Yellow
    Write-Host "  1. Start server: uvicorn rag_agent.api:app --port 8000" -ForegroundColor White
    Write-Host "  2. Run: promptfoo eval -c promptfooconfig.yaml" -ForegroundColor White
    Write-Host ""
    exit 0
}

# Run native benchmark
Write-Host "[1/2] Running native benchmark..." -ForegroundColor Yellow

$cmd = "python -m rag_agent.benchmark"
if ($Limit -gt 0) {
    $cmd += " --limit $Limit"
}

Write-Host "Command: $cmd" -ForegroundColor Gray
Write-Host ""

# Execute benchmark
Invoke-Expression $cmd
$exitCode = $LASTEXITCODE

Write-Host ""

if ($exitCode -eq 0) {
    Write-Host "Benchmark completed successfully!" -ForegroundColor Green
} else {
    Write-Host "Benchmark completed with failures or below threshold." -ForegroundColor Red
}

# Show output files
$outputDir = "benchmark_results"
if (Test-Path $outputDir) {
    Write-Host ""
    Write-Host "Results:" -ForegroundColor Cyan
    Get-ChildItem $outputDir -File | ForEach-Object {
        Write-Host "  - $($_.Name) ($([math]::Round($_.Length/1KB, 1)) KB)" -ForegroundColor White
    }
}

exit $exitCode
