# Getting the platform running - plain English

Everything below is **paper trading**. No real money is involved at any point.
Live trading stays locked behind the separate human approval process in
`RUNBOOK.md`; none of these scripts can turn it on.

---

## Step 1 - run the setup script ONCE

Pick the line that matches how you like to work. Both do exactly the same
thing, printing each step as it happens.

**Easiest (Windows):** open the `scripts` folder in File Explorer and
double-click **`setup.cmd`**.

**Command Prompt (cmd):**

```
cd C:\path\to\trading_platform
scripts\setup.cmd
```

**PowerShell:**

```
cd C:\path\to\trading_platform
powershell -ExecutionPolicy Bypass -File .\scripts\setup.ps1
```

**Linux / macOS / WSL:**

```
cd /path/to/trading_platform
bash scripts/setup.sh
```

What it does, in order:

1. Checks Python 3.11+ is installed
2. Creates a private Python environment in `.venv`
3. Upgrades `pip`
4. Installs the platform packages from `requirements.txt`
5. Installs the test packages from `requirements-dev.txt`
6. Creates your `.env` settings file from `.env.example` (never overwrites one you already have)
7. Starts the database + cache in Docker and applies migrations (skipped cleanly if Docker isn't installed)
8. Runs the test suite so you know the install is healthy

If a step fails, the script stops right there and tells you which step it was.
Fix that one thing and run it again - it is safe to re-run any number of times.

### The one thing you must do by hand

After setup creates `.env`, open it in Notepad and paste your **Alpaca paper**
keys:

```
ALPACA_API_KEY=your_key_here
ALPACA_SECRET_KEY=your_secret_here
TRADING_MODE=PAPER
```

Free keys come from <https://app.alpaca.markets/paper/dashboard/overview>.
Leave `TRADING_MODE=PAPER`.

---

## Step 2 - start the platform whenever you want it

**Windows (double-click or cmd):**

```
scripts\start.cmd
```

**PowerShell:**

```
powershell -ExecutionPolicy Bypass -File .\scripts\start.ps1
```

**Linux / macOS / WSL:**

```
bash scripts/start.sh
```

This starts the database, opens the **trading API** on port 8000, waits until it
actually answers, starts the **paper trading loop**, and opens the API docs in
your browser.

Useful switches:

| What you want | Windows PowerShell | Linux / macOS |
|---|---|---|
| API only, no auto-trading | `start.ps1 -NoPaperLoop` | `start.sh --no-paper` |
| Don't touch Docker | `start.ps1 -NoDocker` | `start.sh --no-docker` |
| Stop everything | close the two windows | `start.sh --stop` |

---

## Step 3 - connecting the dashboard

The dashboard reads all of its numbers from the trading API. It calls the API
through its own `/api/proxy` route, controlled by one setting:

```
TRADING_API_URL=http://127.0.0.1:8000
```

- **Dashboard running on the same machine as the API** - nothing to do. The
  default already points at `http://localhost:8000`.
- **Dashboard hosted online, API on your PC** - the hosted dashboard *cannot*
  see `127.0.0.1` on your computer; that address means "my own machine" to
  whichever server is asking. You have two options:
  1. Run the dashboard locally too, so both sit on the same machine, or
  2. Expose your local API on a public HTTPS address (an ngrok/Cloudflare
     tunnel works) and set `TRADING_API_URL` to that address.

Until the API is reachable, the dashboard falls back to clearly-labelled sample
data rather than showing blanks - look for the "sample data" badge.

---

## What shows real numbers, and when

| Panel | Needs | Shows |
|---|---|---|
| Account, buying power | Alpaca keys | Real paper account, immediately |
| Market prices, regime, volatility, news | Alpaca keys + internet | Real, immediately |
| System status, mode, risk limits | nothing | Real, immediately |
| Trades, equity curve, monthly returns, signals, strategies, research, logs | database running + the paper loop having traded | Empty until then - deliberately empty rather than invented |

An empty table means "nothing has happened yet", never "the feature is broken".

---

## If something goes wrong

| Symptom | Fix |
|---|---|
| `python not found` | Install Python 3.11+ and tick "Add python.exe to PATH" |
| `docker not found` / containers won't start | Open Docker Desktop and wait for "Running", then re-run setup |
| Dashboard shows "sample data" | The API isn't reachable - check the "AI Trader API" window / `.run/api.log` |
| Market prices are empty | Alpaca keys missing or wrong in `.env` |
| PowerShell refuses to run the script | Use the `-ExecutionPolicy Bypass` form shown above |