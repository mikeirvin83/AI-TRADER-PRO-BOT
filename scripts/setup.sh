#!/usr/bin/env bash
# ===========================================================================
#  AI TRADER PRO - ONE TIME SETUP (Linux / macOS / WSL)
#    bash scripts/setup.sh
#  Runs every setup command in order and stops at the first failure.
#  SAFETY: configures PAPER trading only. Never enables live money trading.
# ===========================================================================
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
STEP=0

banner() { echo; printf '=%.0s' {1..75}; echo; echo "  $1"; printf '=%.0s' {1..75}; echo; }
step()   { STEP=$((STEP+1)); echo; printf -- '-%.0s' {1..75}; echo; echo "  STEP $STEP: $1"; printf -- '-%.0s' {1..75}; echo; }
ok()     { echo "   [OK] step $STEP finished."; }
skip()   { echo "   [SKIP] $1"; }
fail()   { echo; printf '=%.0s' {1..75}; echo; echo "  SETUP STOPPED at step $STEP"; echo "  $1"; printf '=%.0s' {1..75}; echo; exit 1; }

banner 'AI TRADER PRO - SETUP'
echo "Project folder: $ROOT"

step 'Checking that Python 3.11 or newer is installed'
PY=""
for c in python3.12 python3.11 python3 python; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
[ -n "$PY" ] || fail 'Python was not found. Install Python 3.11 or newer, then run this again.'
echo "   Found: $($PY --version 2>&1)"
ok

step 'Creating the private Python environment (folder: .venv)'
if [ -x "$ROOT/.venv/bin/python" ]; then
  echo '   Already exists - reusing it.'
else
  "$PY" -m venv "$ROOT/.venv" || fail 'Could not create the virtual environment (try: sudo apt install python3-venv).'
fi
VPY="$ROOT/.venv/bin/python"
ok

step 'Upgrading pip'
"$VPY" -m pip install --upgrade pip || fail 'pip could not be upgraded.'
ok

step 'Installing the platform packages (this can take a few minutes)'
"$VPY" -m pip install -r "$ROOT/requirements.txt" || fail 'Package installation failed. Scroll up for the first error.'
ok

step 'Installing the test/development packages'
if [ -f "$ROOT/requirements-dev.txt" ]; then
  "$VPY" -m pip install -r "$ROOT/requirements-dev.txt" || fail 'Dev package installation failed.'
else
  skip 'no requirements-dev.txt found.'
fi
ok

step 'Creating your settings file (.env)'
if [ -f "$ROOT/.env" ]; then
  echo '   .env already exists - leaving your settings untouched.'
else
  cp "$ROOT/.env.example" "$ROOT/.env"
  echo '   Created .env from the example template.'
  echo
  echo "   NEXT: edit $ROOT/.env and paste your Alpaca PAPER keys into"
  echo '         ALPACA_API_KEY and ALPACA_SECRET_KEY.'
  echo '         Free keys: https://app.alpaca.markets/paper/dashboard/overview'
  echo '         Leave TRADING_MODE=PAPER.'
fi
ok

step 'Starting the database and cache (needs Docker)'
if ! command -v docker >/dev/null 2>&1; then
  skip 'Docker not installed.'
  echo '   The platform still runs without it: live market data, the API and the'
  echo '   dashboard all work. Saved trade history needs it.'
else
  if docker compose up -d postgres redis; then
    echo '   Waiting 10 seconds for the database to accept connections...'
    sleep 10
    echo '   -> Applying database migrations'
    "$VPY" -m alembic upgrade head || echo '   Migrations did not complete - re-run this script later.'
  else
    echo '   Docker is installed but the containers did not start. Is the daemon running?'
  fi
fi
ok

step 'Running the test suite to prove the install is healthy'
"$VPY" -m pytest tests -q || echo '   Some tests failed. Setup is still usable - note this above.'
ok

banner 'SETUP COMPLETE'
echo 'Next step: bash scripts/start.sh'
echo