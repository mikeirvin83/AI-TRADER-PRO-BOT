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
Write-Step 'Checking for a supported Python version (3.11, 3.12 or 3.13)'

function Test-PythonOk($exe, $exeArgs) {
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { return $false }
    & $exe @($exeArgs + @('-c', 'import sys; sys.exit(0 if (3,11) <= sys.version_info < (3,14) else 1)')) 2>$null
    return ($LASTEXITCODE -eq 0)
}

$pyExe = $null
$pyArgs = @()
foreach ($try in @(@('py', @('-3.12')), @('py', @('-3.11')), @('py', @('-3.13')), @('python', @()), @('python3', @()))) {
    if (Test-PythonOk $try[0] $try[1]) { $pyExe = $try[0]; $pyArgs = $try[1]; break }
}

if (-not $pyExe) {
    Write-Host ''
    Write-Host '  ---------------------------------------------------------------' -ForegroundColor Red
    Write-Host '   NO SUPPORTED PYTHON VERSION WAS FOUND' -ForegroundColor Red
    Write-Host '  ---------------------------------------------------------------' -ForegroundColor Red
    Write-Host '   This platform needs Python 3.11, 3.12 or 3.13.'
    Write-Host '   Python 3.14 (and newer) does NOT work yet: the maths packages'
    Write-Host '   have no ready-made build for it, so your PC would try to'
    Write-Host '   compile them from source and fail with a compiler error.'
    Write-Host ''
    Write-Host '   WHAT TO DO (5 minutes):' -ForegroundColor Yellow
    Write-Host '     1. Open https://www.python.org/downloads/release/python-3129/'
    Write-Host '     2. Scroll to the bottom, click "Windows installer (64-bit)"'
    Write-Host '     3. Run it and TICK "Add python.exe to PATH" on the first screen'
    Write-Host '     4. You do NOT need to uninstall the Python you already have'
    Write-Host '     5. Close this window, open a new one, and run this script again'
    Write-Host ''
    Stop-Setup 'Install Python 3.12 (link above) and run this script again.'
}

$verText = & $pyExe @($pyArgs + '--version') 2>&1
Write-Host "   Using: $verText"
Write-Ok

# ------------------------------------------------------------------ step 2 ---
Write-Step 'Creating the private Python environment (folder: .venv)'
$venvPy = Join-Path $Root '.venv\Scripts\python.exe'
if (Test-Path $venvPy) {
    if (Test-PythonOk $venvPy @()) {
        Write-Host '   Already exists - reusing it.'
    } else {
        Write-Host '   The existing .venv was built with an unsupported Python.' -ForegroundColor DarkYellow
        Write-Host '   Deleting it and rebuilding with the good one...' -ForegroundColor DarkYellow
        Remove-Item -Recurse -Force (Join-Path $Root '.venv')
    }
}
if (-not (Test-Path $venvPy)) {
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
& $venvPy -m pip install --prefer-binary -r (Join-Path $Root 'requirements.txt')
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '   If the error above mentions a compiler, "cl", Meson, or' -ForegroundColor DarkYellow
    Write-Host '   "metadata-generation-failed", your Python version is too new.' -ForegroundColor DarkYellow
    Write-Host '   Install Python 3.12 from' -ForegroundColor DarkYellow
    Write-Host '   https://www.python.org/downloads/release/python-3129/' -ForegroundColor DarkYellow
    Write-Host '   then delete the .venv folder and run this script again.' -ForegroundColor DarkYellow
    Stop-Setup 'Package installation failed. Scroll up for the first red error.'
}
Write-Ok

# ------------------------------------------------------------------ step 5 ---
Write-Step 'Installing the test/development packages'
$devReq = Join-Path $Root 'requirements-dev.txt'
if (Test-Path $devReq) {
    & $venvPy -m pip install --prefer-binary -r $devReq
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