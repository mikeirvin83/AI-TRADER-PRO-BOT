@echo off
REM Helper launched by start.cmd in its own window. Do not run directly.
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo [X] The Python environment is missing. Run scripts\setup.cmd first.
  pause
  exit /b 1
)
echo ===========================================================================
echo  AI TRADER API - serving the dashboard on port 8000
echo  Leave this window open. Press Ctrl+C to stop.
echo ===========================================================================
echo.
".venv\Scripts\python.exe" -m uvicorn api.main:app --host 127.0.0.1 --port 8000
echo.
echo ===========================================================================
echo  The API stopped. Any error explaining why is in the lines above.
echo ===========================================================================
pause
