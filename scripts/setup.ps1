# ===========================================================================
#  AI TRADER PRO - ONE TIME SETUP (Windows PowerShell)
#
#  HOW TO RUN:
#    1. Right-click the Start button -> "Terminal" or "Windows PowerShell"
#    2. Paste this line and press Enter:
#         cd "C:\path\to\trading_platform"; powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
#
#  It runs every setup command in order, prints what it is doing, and stops at
#  the first real failure so you always know where you are.
#
#  SAFETY: configures PAPER trading only. Never enables live money trading.
# ===========================================================================

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root
$script:StepNo = 0

function Write-Banner($text) {
    Write-Host ''
    Write-Host ('=' * 75) -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host ('=' * 75) -ForegroundColor Cyan
}

function Write-Step($text) {
    $script:StepNo++
    Write-Host ''
    Write-Host ('-' * 75) -ForegroundColor DarkGray
    Write-Host "  STEP $($script:StepNo): $text" -ForegroundColor Yellow
    Write-Host ('-' * 75) -ForegroundColor DarkGray
}

function Write-Ok { Write-Host "   [OK] step $($script:StepNo) finished." -ForegroundColor Green }
function Write-Skip($t) { Write-Host "   [SKIP] $t" -ForegroundColor DarkYellow }

function Stop-Setup($text) {
    Write-Host ''
    Write-Host ('=' * 75) -ForegroundColor Red
    Write-Host "  SETUP STOPPED at step $($script:StepNo)" -ForegroundColor Red
    Write-Host "  $text" -ForegroundColor Red
    Write-Host ('=' * 75) -ForegroundColor Red
    exit 1
}

Write-Banner 'AI TRADER PRO - SETUP'
Write-Host "Project folder: $Root"

# ------------------------------------------------------------------ step 1 ---
Write-Step 'Checking that Python 3.11 or newer is installed'
$pyExe = $null
foreach ($candidate in @('py', 'python', 'python3')) {
    $cmd = Get-Command $candidate -ErrorAction SilentlyContinue
    if ($cmd) { $pyExe = $candidate; break }
}
if (-not $pyExe) {
    Stop-Setup 'Python was not found. Install Python 3.11+ from https://www.python.org/downloads/ and tick "Add python.exe to PATH", then run this again.'
}
if ($pyExe -eq 'py') { $pyArgs = @('-3') } else { $pyArgs = @() }
$verText = & $pyExe @($pyArgs + '--version') 2>&1
Write-Host "   Found: $verText"
Write-Ok

# ------------------------------------------------------------------ step 2 ---
Write-Step 'Creating the private Python environment (folder: .venv)'
$venvPy = Join-Path $Root '.venv\Scripts\python.exe'
if (Test-Path $venvPy) {
    Write-Host '   Already exists - reusing it.'
} else {
    & $pyExe @($pyArgs + @('-m', 'venv', (Join-Path $Root '.venv')))
    if (-not (Test-Path $venvPy)) { Stop-Setup 'The virtual environment was not created.' }
}
Write-Ok

# ------------------------------------------------------------------ step 3 ---
Write-Step 'Upgrading pip'
& $venvPy -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { Stop-Setup 'pip could not be upgraded.' }
Write-Ok

# ------------------------------------------------------------------ step 4 ---
Write-Step 'Installing the platform packages (this can take a few minutes)'
& $venvPy -m pip install -r (Join-Path $Root 'requirements.txt')
if ($LASTEXITCODE -ne 0) { Stop-Setup 'Package installation failed. Scroll up for the first red error.' }
Write-Ok

# ------------------------------------------------------------------ step 5 ---
Write-Step 'Installing the test/development packages'
$devReq = Join-Path $Root 'requirements-dev.txt'
if (Test-Path $devReq) {
    & $venvPy -m pip install -r $devReq
    if ($LASTEXITCODE -ne 0) { Stop-Setup 'Dev package installation failed.' }
} else {
    Write-Skip 'no requirements-dev.txt found.'
}
Write-Ok

# ------------------------------------------------------------------ step 6 ---
Write-Step 'Creating your settings file (.env)'
$envFile = Join-Path $Root '.env'
if (Test-Path $envFile) {
    Write-Host '   .env already exists - leaving your settings untouched.'
} else {
    Copy-Item (Join-Path $Root '.env.example') $envFile
    Write-Host '   Created .env from the example template.'
    Write-Host ''
    Write-Host '   NEXT: open this file and paste your Alpaca PAPER keys:' -ForegroundColor Yellow
    Write-Host "         $envFile"
    Write-Host '         ALPACA_API_KEY=...   ALPACA_SECRET_KEY=...'
    Write-Host '         Free keys: https://app.alpaca.markets/paper/dashboard/overview'
    Write-Host '         Leave TRADING_MODE=PAPER.'
}
Write-Ok

# ------------------------------------------------------------------ step 7 ---
Write-Step 'Starting the database and cache (needs Docker Desktop running)'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Skip 'Docker not installed.'
    Write-Host '   The platform still runs without it: live market data, the API and'
    Write-Host '   the dashboard all work. Saved trade history needs it, so you can'
    Write-Host '   install Docker Desktop later and re-run this script.'
} else {
    docker compose up -d postgres redis
    if ($LASTEXITCODE -ne 0) {
        Write-Host '   Docker is installed but the containers did not start.' -ForegroundColor DarkYellow
        Write-Host '   Open Docker Desktop, wait until it says "Running", then re-run this.' -ForegroundColor DarkYellow
    } else {
        Write-Host '   Waiting 10 seconds for the database to accept connections...'
        Start-Sleep -Seconds 10
        Write-Host '   -> Applying database migrations'
        & $venvPy -m alembic upgrade head
        if ($LASTEXITCODE -ne 0) {
            Write-Host '   Migrations did not complete - you can re-run this script later.' -ForegroundColor DarkYellow
        }
    }
}
Write-Ok

# ------------------------------------------------------------------ step 8 ---
Write-Step 'Running the test suite to prove the install is healthy'
& $venvPy -m pytest tests -q
if ($LASTEXITCODE -ne 0) {
    Write-Host '   Some tests failed. Setup is still usable - note this above.' -ForegroundColor DarkYellow
} 
Write-Ok

Write-Banner 'SETUP COMPLETE'
Write-Host 'Next step: run the start script:' -ForegroundColor Green
Write-Host '   powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1'
Write-Host ''