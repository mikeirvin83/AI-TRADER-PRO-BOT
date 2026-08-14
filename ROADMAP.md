# Roadmap

Phased build plan for the Autonomous Adaptive Trading Intelligence Platform.

**Legend:** ✅ done · 🟡 in progress · ⬜ planned

This scaffold delivers the **foundation through control-plane** layers as
importable, tested modules. Later phases turn the scaffold into a fully
operational, promoted-to-live system.

---

### Phase 0 — Foundation ✅
- ✅ Typed settings (`config/settings.py`) with secret resolution (env → secrets file).
- ✅ Domain constants & enums, `FUTURES_SPECS` (MES/MNQ/MYM/M2K).
- ✅ Structured logging (`structlog`).
- ✅ Thread-safe `SystemState` machine, kill switch, transition audit.
- ✅ Async event bus and market clock.

### Phase 1 — Data & persistence ✅
- ✅ 26-table SQLAlchemy model with UUID PKs, timestamps, indexes.
- ✅ Session management + repositories.
- ✅ Alembic migration environment wired to settings + model metadata.
- ⬜ Generate the initial migration revision and apply to PostgreSQL.
- ⬜ Time-series retention / partitioning policy for OHLCV.

### Phase 2 — Market data ingestion ✅ (scaffold)
- ✅ Alpaca client (SDK-optional, retry/backoff).
- ✅ Data-quality validator (`CLEAN`/`WARNING`/`CORRUPTED`).
- ✅ Historical service + `FuturesDataProvider` abstraction.
- ✅ Stream manager + asset universe.
- ⬜ Concrete streaming wiring and persistence of live bars.
- ⬜ Concrete `FuturesDataProvider` implementation for MES/MNQ/MYM/M2K.

### Phase 3 — Feature engineering ✅
- ✅ From-scratch indicators (trend, momentum, volatility, volume, price
  structure, market profile, fair value).
- ✅ `FeatureEngine` producing a unified `FeatureResult`.
- ⬜ Feature caching / incremental computation for live use.

### Phase 4 — Regime & news ✅ (scaffold)
- ✅ `RegimeClassifier` (10 regimes) + regime history.
- ✅ News fetch/classify + economic calendar.
- ⬜ Train/validate a data-driven regime model; connect a real news feed.

### Phase 5 — Strategies ✅
- ✅ `BaseStrategy` + self-validating `StrategySignal`.
- ✅ 17 strategies (trend ×4, momentum ×4, mean-reversion ×4, breakout ×4,
  cross-market).
- ⬜ Expand library; per-strategy parameter optimization under overfitting guard.

### Phase 6 — Signals ✅
- ✅ Unified 0–100 scorer with quality classification.
- ✅ Multi-timeframe confirmation + signal generator.
- ⬜ Calibrate component weights from realized outcomes.

### Phase 7 — Risk & sizing ✅
- ✅ Risk engine (10 checks) with absolute veto + circuit breaker.
- ✅ Position sizer (fixed/ATR/vol-adjusted/futures) with position cap.
- ✅ Correlation engine + drawdown monitor.
- ⬜ Live portfolio-state feed into the risk engine.

### Phase 8 — Execution ✅ (scaffold)
- ✅ Deterministic paper engine.
- ✅ Alpaca executor (shadow/live, SDK-optional).
- ✅ Order manager with duplicate protection + reconciliation.
- ⬜ Live order lifecycle handling (partial fills, cancels, retries) against Alpaca.

### Phase 9 — Backtesting & research ✅
- ✅ No-look-ahead backtest engine (next-bar-open fills).
- ✅ Metrics suite, Monte-Carlo, walk-forward.
- ✅ Hypothesis manager, overfitting detector, strategy comparator.
- ⬜ Backtest data pipeline over persisted history; experiment tracking UI.

### Phase 10 — Memory, learning & agents ✅ (scaffold)
- ✅ Knowledge store, trade memory, learning engine.
- ✅ 10 specialized agents (incl. risk-manager & strategy-governor vetoes).
- ✅ Decision loop + daily/weekly reviews.
- ⬜ Close the learning loop end-to-end against live paper results.

### Phase 11 — Control plane & alerts ✅
- ✅ FastAPI app with system/account/positions/strategies/signals/risk/research
  routers + `/health`.
- ✅ Configurable alert manager (log + webhook channels, severity-aware).
- ⬜ AuthN/Z on the API; dashboard UI; Prometheus metrics endpoint.

### Phase 12 — Hardening & promotion ⬜
- ⬜ Run in `PAPER` and meet promotion gates (`MIN_PAPER_TRADES`,
  `MIN_PAPER_DURATION_DAYS`).
- ⬜ Promote `PAPER → SHADOW`; validate shadow vs. live divergence.
- ⬜ Operational runbooks, monitoring, and on-call alerting.
- ⬜ Only then consider human-approved `SHADOW → LIVE`.

---

## Current status summary

| Layer | Status |
|-------|--------|
| Foundation (config/core) | ✅ complete |
| Data & persistence | ✅ scaffold; migration/apply pending |
| Market data | ✅ scaffold; live wiring + futures provider pending |
| Features | ✅ complete |
| Regime & news | ✅ scaffold; real feeds/models pending |
| Strategies | ✅ 17 implemented |
| Signals | ✅ complete |
| Risk & sizing | ✅ complete |
| Execution | ✅ scaffold; live lifecycle pending |
| Backtesting & research | ✅ complete |
| Memory/learning/agents | ✅ scaffold; loop closure pending |
| API & alerts | ✅ complete; auth/UI/metrics pending |
| Promotion to live | ⬜ gated, not started |

**Test suite:** unit + integration tests pass with no live broker or database.

The scaffold is import-clean and runnable in `PAPER` mode today; the ⬜ items are
the path to a fully operational, safely promoted live system.
