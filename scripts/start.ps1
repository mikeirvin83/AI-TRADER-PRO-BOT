# ===========================================================================
#  AI TRADER PRO - START EVERYTHING (Windows PowerShell)
#
#  Run scripts\setup.ps1 once first. Then, whenever you want the platform up:
#     powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
#
#  Options:
#     -NoPaperLoop    start only the API (no automatic trade scanning)
#     -NoDocker       skip starting the database/cache containers
#
#  SAFETY: starts in PAPER mode only. No real money is ever at risk.
# ===========================================================================
param(
    [switch]$NoPaperLoop,
    [switch]$NoDocker
)

$ErrorActionPreference = 'Continue'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

Write-Host ''
Write-Host ('=' * 75) -ForegroundColor Cyan
Write-Host '  AI TRADER PRO - STARTING (PAPER MODE)' -ForegroundColor Cyan
Write-Host ('=' * 75) -ForegroundColor Cyan
Write-Host "Project folder: $Root"

$venvPy = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path $venvPy)) {
    Write-Host ''
    Write-Host '[X] The Python environment is missing. Run scripts\setup.ps1 first.' -ForegroundColor Red
    exit 1
}

Write-Host ''
Write-Host 'STEP 1: Database and cache' -ForegroundColor Yellow
if ($NoDocker) {
    Write-Host '   Skipped (-NoDocker).'
} elseif (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host '   Docker not installed - skipping (the API still works).'
} else {
    docker compose up -d postgres redis
}

Write-Host ''
Write-Host 'STEP 2: Opening a window for the trading API (port 8000)' -ForegroundColor Yellow
Start-Process -FilePath 'cmd.exe' -ArgumentList @(
    '/k', "title AI Trader API && cd /d `"$Root`" && `"$venvPy`" -m uvicorn api.main:app --host 127.0.0.1 --port 8000"
)

Write-Host ''
Write-Host 'STEP 3: Waiting for the API to answer (first start can take a minute)...' -ForegroundColor Yellow
$up = $false
for ($i = 1; $i -le 60; $i++) {
    Start-Sleep -Seconds 2
    try {
        $r = Invoke-WebRequest -Uri 'http://127.0.0.1:8000/health' -UseBasicParsing -TimeoutSec 3
        if ($r.StatusCode -eq 200) { $up = $true; break }
    } catch { }
    Write-Host "   ...still loading ($i of 60)"
}
if ($up) {
    Write-Host '   API is up.' -ForegroundColor Green
} else {
    Write-Host '   API still not answering after 2 minutes.' -ForegroundColor DarkYellow
    Write-Host '   Look at the "AI Trader API" window - the last red lines say why.' -ForegroundColor DarkYellow
    Write-Host '   Most common cause: Alpaca keys missing from the .env file.' -ForegroundColor DarkYellow
}

Write-Host ''
Write-Host 'STEP 4: Paper trading loop' -ForegroundColor Yellow
if ($NoPaperLoop) {
    Write-Host '   Skipped (-NoPaperLoop).'
} else {
    Start-Process -FilePath 'cmd.exe' -ArgumentList @(
        '/k', "title AI Trader Paper Loop && cd /d `"$Root`" && `"$venvPy`" run_paper.py"
    )
    Write-Host '   Started in its own window.'
}

Write-Host ''
Write-Host 'STEP 5: Opening the API docs in your browser' -ForegroundColor Yellow
Start-Process 'http://127.0.0.1:8000/docs'

Write-Host ''
Write-Host ('=' * 75) -ForegroundColor Green
Write-Host '  RUNNING. New windows are open:' -ForegroundColor Green
Write-Host '    * "AI Trader API"        - serves data to the dashboard (port 8000)'
Write-Host '    * "AI Trader Paper Loop" - scans the market, places PAPER trades'
Write-Host ''
Write-Host '  To stop: press Ctrl+C in each window, or close them.'
Write-Host '  Dashboard connection notes: scripts\README-SCRIPTS.md'
Write-Host ('=' * 75) -ForegroundColor Green
Write-Host ''