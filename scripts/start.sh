#!/usr/bin/env bash
# ===========================================================================
#  AI TRADER PRO - START EVERYTHING (Linux / macOS / WSL)
#    bash scripts/start.sh                # API + paper loop
#    bash scripts/start.sh --no-paper     # API only
#    bash scripts/start.sh --no-docker    # skip database/cache containers
#    bash scripts/start.sh --stop         # stop what this script started
#  SAFETY: starts in PAPER mode only. No real money is ever at risk.
# ===========================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
RUN_DIR="$ROOT/.run"
mkdir -p "$RUN_DIR"

WANT_PAPER=1
WANT_DOCKER=1
for arg in "$@"; do
  case "$arg" in
    --no-paper)  WANT_PAPER=0 ;;
    --no-docker) WANT_DOCKER=0 ;;
    --stop)
      for name in api paper; do
        pf="$RUN_DIR/$name.pid"
        if [ -f "$pf" ] && kill -0 "$(cat "$pf")" 2>/dev/null; then
          kill "$(cat "$pf")" && echo "Stopped $name (pid $(cat "$pf"))"
        else
          echo "$name was not running."
        fi
        rm -f "$pf"
      done
      exit 0 ;;
  esac
done

echo
printf '=%.0s' {1..75}; echo
echo '  AI TRADER PRO - STARTING (PAPER MODE)'
printf '=%.0s' {1..75}; echo
echo "Project folder: $ROOT"

VPY="$ROOT/.venv/bin/python"
if [ ! -x "$VPY" ]; then
  if command -v python3 >/dev/null 2>&1; then
    echo '   No .venv found - falling back to the system python3.'
    VPY="$(command -v python3)"
  else
    echo '[X] No Python environment. Run: bash scripts/setup.sh'
    exit 1
  fi
fi

echo
echo 'STEP 1: Database and cache'
if [ "$WANT_DOCKER" -eq 0 ]; then
  echo '   Skipped (--no-docker).'
elif ! command -v docker >/dev/null 2>&1; then
  echo '   Docker not installed - skipping (the API still works).'
else
  docker compose up -d postgres redis || echo '   Containers did not start - continuing.'
fi

echo
echo 'STEP 2: Starting the trading API on port 8000'
nohup "$VPY" -m uvicorn api.main:app --host 127.0.0.1 --port 8000 > "$RUN_DIR/api.log" 2>&1 &
echo $! > "$RUN_DIR/api.pid"
echo "   pid $(cat "$RUN_DIR/api.pid")  log: $RUN_DIR/api.log"

echo
echo 'STEP 3: Waiting for the API to answer...'
UP=0
for _ in $(seq 1 20); do
  sleep 2
  if curl -fsS -o /dev/null http://127.0.0.1:8000/health 2>/dev/null; then UP=1; break; fi
done
if [ "$UP" -eq 1 ]; then
  echo '   API is up.'
else
  echo "   API did not answer. Check $RUN_DIR/api.log"
fi

echo
echo 'STEP 4: Paper trading loop'
if [ "$WANT_PAPER" -eq 0 ]; then
  echo '   Skipped (--no-paper).'
else
  nohup "$VPY" run_paper.py > "$RUN_DIR/paper.log" 2>&1 &
  echo $! > "$RUN_DIR/paper.pid"
  echo "   pid $(cat "$RUN_DIR/paper.pid")  log: $RUN_DIR/paper.log"
fi

echo
printf '=%.0s' {1..75}; echo
echo '  RUNNING (PAPER MODE)'
echo "    API docs:  http://127.0.0.1:8000/docs"
echo "    API log:   $RUN_DIR/api.log"
echo "    Loop log:  $RUN_DIR/paper.log"
echo
echo '  Stop everything with:  bash scripts/start.sh --stop'
printf '=%.0s' {1..75}; echo
echo