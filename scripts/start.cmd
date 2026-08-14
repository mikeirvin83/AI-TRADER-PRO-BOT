@echo off
REM ===========================================================================
REM  AI TRADER PRO - START EVERYTHING (Windows / cmd.exe)
REM  Run scripts\setup.cmd once first, then use this file every time you want
REM  the platform running.
REM  SAFETY: starts in PAPER mode only. No real money is ever at risk here.
REM ===========================================================================
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"

echo.
echo ===========================================================================
echo  AI TRADER PRO - STARTING (PAPER MODE)
echo ===========================================================================
echo Project folder: %ROOT%

if not exist "%ROOT%\.venv\Scripts\python.exe" (
  echo.
  echo [X] The Python environment is missing.
  echo     Run scripts\setup.cmd first.
  pause
  exit /b 1
)
set "VPY=%ROOT%\.venv\Scripts\python.exe"

echo.
echo STEP 1: Starting the database and cache (skipped if Docker is not installed)
docker --version >nul 2>&1
if errorlevel 1 (
  echo    Docker not found - skipping.
) else (
  docker compose up -d postgres redis
)

echo.
echo STEP 2: Opening a window for the trading API (port 8000)
start "AI Trader API" cmd /k "cd /d "%ROOT%" ^&^& ".venv\Scripts\python.exe" -m uvicorn api.main:app --host 127.0.0.1 --port 8000"

echo.
echo STEP 3: Waiting for the API to answer...
set "TRIES=0"
:waitapi
set /a TRIES+=1
timeout /t 2 /nobreak >nul
curl -s -o nul http://127.0.0.1:8000/health
if not errorlevel 1 goto :apiup
if %TRIES% GEQ 15 (
  echo    API did not answer yet. Check the "AI Trader API" window for errors.
  goto :apidone
)
goto :waitapi
:apiup
echo    API is up.
:apidone

echo.
echo STEP 4: Opening a window for the paper trading loop
start "AI Trader Paper Loop" cmd /k "cd /d "%ROOT%" ^&^& ".venv\Scripts\python.exe" run_paper.py"

echo.
echo STEP 5: Opening the API docs in your browser
start "" http://127.0.0.1:8000/docs

echo.
echo ===========================================================================
echo  RUNNING. Two new windows are now open:
echo    * "AI Trader API"         - serves data to the dashboard (port 8000)
echo    * "AI Trader Paper Loop"  - scans the market and places PAPER trades
echo.
echo  To stop: press Ctrl+C in each window, or just close them.
echo.
echo  Your dashboard reads from this API. If the dashboard is hosted online
echo  it cannot see 127.0.0.1 on this PC - see scripts\README-SCRIPTS.md.
echo ===========================================================================
echo.
pause
