# Autonomous Adaptive Trading Intelligence Platform

A modular, **risk-first**, self-improving trading system for US equities, ETFs,
crypto and CME micro futures. The platform researches, backtests, scores and
(optionally) executes trades through a governed promotion pipeline — and never
skips a safety gate.

> **Safety posture:** the system **defaults to `PAPER` mode** and can only be
> promoted **`PAPER → SHADOW → LIVE`**, one step at a time, by a human. The
> **risk engine holds absolute veto authority** over every order, and a
> **kill switch** halts trading instantly at every layer. No market data,
> prices, fills or broker capabilities are ever fabricated.

---

## Table of contents
1. [Key principles](#key-principles)
2. [What's in this scaffold](#whats-in-this-scaffold)
3. [Architecture at a glance](#architecture-at-a-glance)
4. [Repository layout](#repository-layout)
5. [Getting started](#getting-started)
6. [Configuration & secrets](#configuration--secrets)
7. [Running the API](#running-the-api)
8. [Trading modes & the promotion pipeline](#trading-modes--the-promotion-pipeline)
9. [Risk management](#risk-management)
10. [Futures support](#futures-support)
11. [Testing](#testing)
12. [Docker](#docker)
13. [Further reading](#further-reading)

---

## Key principles

| Principle | How it is enforced |
|-----------|--------------------|
| **Paper by default** | `TRADING_MODE` defaults to `PAPER`; `LIVE` is never implicit. |
| **Gated promotion** | `PAPER → SHADOW → LIVE` only. Illegal jumps raise `IllegalTransitionError`. |
| **Risk has veto** | `RiskEngine.check_trade()` must approve *every* order; it can also trip a circuit breaker. |
| **Global kill switch** | `SystemState.engage_emergency_stop()` halts trading everywhere at once. |
| **No hallucinated data** | Alpaca paths are SDK-optional and fail *soft*; missing data → no trade, never a fake fill. |
| **Everything observable** | Structured logging (`structlog`) across all modules; audit trail of every mode change. |
| **Config, not constants** | Every risk limit and threshold comes from `config/settings.py` / env — nothing hardcoded. |

## What's in this scaffold

This repository is a **complete, importable project scaffold** — every module
imports cleanly and the test suite passes. It includes:

- Typed settings & constants, structured logging, a thread-safe system-state
  machine, an async event bus and a market clock.
- A full SQLAlchemy data model (26 tables) with repositories, session
  management and an Alembic migration environment.
- Market-data ingestion (Alpaca, SDK-optional), a data-quality validator, and a
  pluggable `FuturesDataProvider` abstraction.
- A from-scratch indicator library (trend, momentum, volatility, volume, price
  structure, market profile, fair value) feeding a `FeatureEngine`.
- A market-regime classifier, news/economic-calendar analysis, 17 strategies
  across trend / momentum / mean-reversion / breakout / cross-market families.
- A unified 0–100 signal scorer, multi-timeframe confirmation, and a signal
  generator.
- A **risk engine** (per-trade, position, leverage, correlation, daily/weekly
  loss, drawdown limits + circuit breaker), position sizer (incl. futures),
  correlation engine and drawdown monitor.
- Execution layer: deterministic paper engine, Alpaca executor (shadow/live),
  and an order manager with duplicate protection.
- Backtesting (no look-ahead, next-bar-open fills), Monte-Carlo and
  walk-forward analysis, plus a full performance-metrics suite.
- A research toolkit (hypothesis manager, overfitting detector, strategy
  comparator), a memory/learning subsystem, and **10 specialized agents** with a
  decision loop and daily/weekly reviews.
- A FastAPI control plane and a configurable alerting subsystem.

See [`ARCHITECTURE.md`](ARCHITECTURE.md) for the deep dive and
[`ROADMAP.md`](ROADMAP.md) for build status and phasing.

## Architecture at a glance

```
  Market Data ─▶ Validation ─▶ Features ─▶ Regime ─┐
      (Alpaca / Futures provider)                  │
                                          News ─────┤
                                                    ▼
                                             Strategies (17)
                                                    │
                                                    ▼
                                        Signal Scoring & MTF
                                                    │
                                                    ▼
                              ┌────────────  RISK ENGINE (veto)  ◀── Kill switch
                              │                     │
                              ▼                     ▼
                        (rejected)          Order Manager
                                                    │
                              ┌─────────────────────┼─────────────────────┐
                              ▼                     ▼                     ▼
                         Paper Engine        Shadow (log-only)      Live (Alpaca)
                              │                     │                     │
                              └──────────▶ Trades ◀─┴─────────────────────┘
                                                    │
                                     Memory / Learning ─▶ Research ─▶ (improve strategies)
```

The **agent layer** (market scanner, regime analyst, news analyst, quant
researcher, backtesting agent, risk manager, execution agent, trade reviewer,
learning agent, strategy governor) coordinates the flow above through the
`orchestration/decision_loop.py`.

## Repository layout

```
trading_platform/
├── config/          # settings, constants, logging
├── core/            # system state, event bus, clock
├── database/        # models, session, repositories, migrations
├── market_data/     # alpaca client, validator, historical, streaming, universe
├── features/        # indicators + feature engine (implemented from scratch)
├── regime/          # market-regime classifier + history
├── news/            # news fetch/classify + economic calendar
├── strategies/      # base + trend/momentum/mean_reversion/breakout/cross_market
├── signals/         # scorer, multi-timeframe, generator
├── risk/            # risk engine, position sizer, correlation, drawdown
├── execution/       # paper engine, alpaca executor, order manager
├── backtesting/     # engine, metrics, monte carlo, walk forward
├── research/        # hypothesis manager, overfitting detector, comparator
├── memory/          # knowledge store, trade memory, learning engine
├── agents/          # 10 specialized agents + base
├── orchestration/   # decision loop, daily/weekly review
├── api/             # FastAPI app, routers, schemas
├── alerts/          # alert manager + channels
└── tests/           # unit + integration tests
```

## Getting started

```bash
# 1. Python 3.11+
python --version

# 2. Install dependencies
pip install -r requirements.txt -r requirements-dev.txt

# 3. Copy and edit environment config
cp .env.example .env

# 4. Run the tests
pytest
```

## Configuration & secrets

All configuration is centralized in [`config/settings.py`](config/settings.py)
(a Pydantic `BaseSettings`). Values are read from environment variables / `.env`.

**Alpaca credentials** are resolved by `Settings.resolve_alpaca_credentials()`
in this order:

1. `ALPACA_API_KEY` / `ALPACA_SECRET_KEY` environment variables, then
2. the platform secrets file (`/home/ubuntu/.config/abacusai_auth_secrets.json`),
   read case-insensitively.

Secrets are **never** hardcoded and `.env` is git-ignored. The base URL defaults
to the **paper** endpoint (`https://paper-api.alpaca.markets`).

## Running the API

```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

- Interactive docs: `http://localhost:8000/docs`
- Health check: `http://localhost:8000/health`
- Mode & kill-switch control: `POST /system/mode`, `POST /system/kill`

## Trading modes & the promotion pipeline

```
DISABLED ─▶ RESEARCH ─▶ BACKTEST ─▶ PAPER ─▶ SHADOW ─▶ LIVE
                                      ▲          │          │
                                      └──────────┴──────────┘  (demote any time)
                     EMERGENCY_STOP ◀── (from anywhere; reset → DISABLED only)
```

- **DISABLED / RESEARCH / BACKTEST** — no live orders.
- **PAPER** *(default)* — simulated fills via the deterministic paper engine.
- **SHADOW** — real signals logged against the live market but **not sent** to
  the broker (used to validate before going live).
- **LIVE** — orders routed to Alpaca (requires the SDK + credentials).
- Skipping a step (e.g. `PAPER → LIVE`) is rejected. Promotion gates
  (`MIN_PAPER_TRADES`, `MIN_PAPER_DURATION_DAYS`) guard the path.

## Risk management

`risk/risk_engine.py` evaluates **every** prospective trade against:

- max risk per trade, max position size, max simultaneous trades,
- max leverage, max correlated-cluster exposure,
- daily / weekly loss limits, and peak-to-trough portfolio drawdown.

A breach of a hard loss threshold trips the **circuit breaker**, which engages
the global emergency stop. All limits are configurable in `settings.py`.

## Futures support

Alpaca does **not** provide futures data or execution, so futures are handled
through a pluggable `FuturesDataProvider` abstraction
(`market_data/historical.py`) — no fabricated data. Contract specifications for
the CME/CBOT micros are defined in `config/constants.py`:

| Symbol | Market | Tick size | $/tick | $/point |
|--------|--------|-----------|--------|---------|
| MES | Micro E-mini S&P 500 | 0.25 | $1.25 | $5 |
| MNQ | Micro E-mini Nasdaq-100 | 0.25 | $0.50 | $2 |
| MYM | Micro E-mini Dow | 1.0 | $0.50 | $0.50 |
| M2K | Micro E-mini Russell 2000 | 0.10 | $0.50 | $5 |

The position sizer uses these specs to size in **contracts** from tick risk.

## Testing

```bash
pytest            # run everything
pytest -v         # verbose
pytest tests/test_risk_engine.py
```

The suite covers indicators (known values), risk vetoes & circuit breaker,
position sizing (incl. futures), the kill switch & mode transitions, signal
scoring, data validation, order management and the backtest engine. Tests use no
live broker or database.

## Docker

```bash
docker compose up --build
```

Brings up the API (`:8000`), PostgreSQL (`:5432`), Redis (`:6379`) and pgAdmin
(`:5050`), all in `PAPER` mode with health checks.

## Further reading

- [`ARCHITECTURE.md`](ARCHITECTURE.md) — full design, data flow, ERD, agent
  architecture, risk architecture, Alpaca integration plan & security model.
- [`ROADMAP.md`](ROADMAP.md) — phased build plan and current status.

---

**Disclaimer:** This software is for research and educational purposes. Trading
involves substantial risk of loss. Nothing here is financial advice. Operate in
`PAPER` mode until you fully understand the system and have completed every
promotion gate.
