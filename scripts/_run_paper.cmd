@echo off
REM Helper launched by start.cmd in its own window. Do not run directly.
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo [X] The Python environment is missing. Run scripts\setup.cmd first.
  pause
  exit /b 1
)
echo ===========================================================================
echo  AI TRADER PAPER LOOP - scans the market and places PAPER trades only
echo  Leave this window open. Press Ctrl+C to stop.
echo ===========================================================================
echo.
".venv\Scripts\python.exe" run_paper.py
echo.
echo ===========================================================================
echo  The paper loop stopped. Any error explaining why is in the lines above.
echo ===========================================================================
pause
