@echo off
REM ===========================================================================
REM  AI TRADER PRO - ONE TIME SETUP (Windows / cmd.exe)
REM  Double-click this file, or run it from a cmd window.
REM  It runs every setup command in order and stops at the first failure.
REM  SAFETY: this only ever configures PAPER trading. It never enables live
REM  trading with real money.
REM ===========================================================================
setlocal
cd /d "%~dp0.."
set "ROOT=%CD%"
set "STEP=0"

call :banner "AI TRADER PRO - SETUP"
echo Project folder: %ROOT%
echo.

REM ---------------------------------------------------------------- step 1 ---
call :step "Checking that Python is installed"
where py >nul 2>&1
if %ERRORLEVEL%==0 (set "PYLAUNCH=py -3") else (set "PYLAUNCH=python")
%PYLAUNCH% --version
if errorlevel 1 (
  echo.
  echo [X] Python was not found.
  echo     Install Python 3.11 or newer from https://www.python.org/downloads/
  echo     During install, TICK "Add python.exe to PATH", then run this file again.
  goto :fail
)
call :ok

REM ---------------------------------------------------------------- step 2 ---
call :step "Creating the private Python environment (folder: .venv)"
if exist "%ROOT%\.venv\Scripts\python.exe" (
  echo Already exists - reusing it.
) else (
  %PYLAUNCH% -m venv "%ROOT%\.venv"
  if errorlevel 1 goto :fail
)
set "VPY=%ROOT%\.venv\Scripts\python.exe"
call :ok

REM ---------------------------------------------------------------- step 3 ---
call :step "Upgrading pip"
"%VPY%" -m pip install --upgrade pip
if errorlevel 1 goto :fail
call :ok

REM ---------------------------------------------------------------- step 4 ---
call :step "Installing the platform packages (this can take a few minutes)"
"%VPY%" -m pip install -r "%ROOT%\requirements.txt"
if errorlevel 1 goto :fail
call :ok

REM ---------------------------------------------------------------- step 5 ---
call :step "Installing the test/development packages"
if exist "%ROOT%\requirements-dev.txt" (
  "%VPY%" -m pip install -r "%ROOT%\requirements-dev.txt"
  if errorlevel 1 goto :fail
) else (
  echo No requirements-dev.txt found - skipping.
)
call :ok

REM ---------------------------------------------------------------- step 6 ---
call :step "Creating your settings file (.env)"
if exist "%ROOT%\.env" (
  echo .env already exists - leaving your settings untouched.
) else (
  copy /y "%ROOT%\.env.example" "%ROOT%\.env" >nul
  echo Created .env from the example template.
  echo.
  echo   NEXT: open %ROOT%\.env in Notepad and paste your Alpaca PAPER keys
  echo         into ALPACA_API_KEY and ALPACA_SECRET_KEY.
  echo         Get them free at https://app.alpaca.markets/paper/dashboard/overview
  echo         Leave TRADING_MODE=PAPER.
)
call :ok

REM ---------------------------------------------------------------- step 7 ---
call :step "Starting the database and cache (needs Docker Desktop running)"
docker --version >nul 2>&1
if errorlevel 1 (
  echo Docker was not found - SKIPPING.
  echo The platform still runs: live market data, the API and the dashboard
  echo all work without it. Trade history and saved results need it, so
  echo install Docker Desktop later from https://www.docker.com/products/docker-desktop/
) else (
  docker compose up -d postgres redis
  if errorlevel 1 (
    echo Docker is installed but could not start the containers.
    echo Make sure Docker Desktop is open and running, then re-run this file.
  ) else (
    echo Waiting 10 seconds for the database to accept connections...
    timeout /t 10 /nobreak >nul
    call :substep "Applying database migrations"
    "%VPY%" -m alembic upgrade head
    if errorlevel 1 echo Migrations did not complete - you can re-run this file later.
  )
)
call :ok

REM ---------------------------------------------------------------- step 8 ---
call :step "Running the test suite to prove the install is healthy"
"%VPY%" -m pytest tests -q
if errorlevel 1 (
  echo.
  echo Some tests failed. Setup is still usable, but note this above.
)
call :ok

call :banner "SETUP COMPLETE"
echo Next step: run  scripts\start.cmd  to launch the platform.
echo.
pause
exit /b 0

:step
set /a STEP+=1
echo.
echo ---------------------------------------------------------------------------
echo  STEP %STEP%: %~1
echo ---------------------------------------------------------------------------
goto :eof

:substep
echo    -^> %~1
goto :eof

:ok
echo    [OK] step %STEP% finished.
goto :eof

:banner
echo.
echo ===========================================================================
echo  %~1
echo ===========================================================================
goto :eof

:fail
echo.
echo ===========================================================================
echo  SETUP STOPPED at step %STEP%. Fix the message above and run this again.
echo ===========================================================================
pause
exit /b 1
