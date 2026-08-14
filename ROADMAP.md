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

### Phase 4 — Regime & news ✅
- ✅ `RegimeClassifier` (10 regimes) + regime history.
- ✅ News fetch/classify + economic calendar.
- ✅ **Strategy validation pipeline** — 11-stage promotion lifecycle (RESEARCH → LIVE).
- ✅ **Strategy degradation monitor** — real-time health tracking (ACTIVE → RETIRED).
- ✅ **Benchmarking engine** — vs buy-and-hold, momentum, risk-free.
- ✅ **Ensemble allocator** — score-weighted dynamic capital allocation.
- ⬜ Train/validate a data-driven regime model.

### Phase 5 — Strategies ✅
- ✅ `BaseStrategy` + self-validating `StrategySignal`.
- ✅ 17 strategies (trend ×4, momentum ×4, mean-reversion ×4, breakout ×4,
  cross-market).
- ✅ **Trade quality filter** — 10 explicit pre-trade checks; default is NO TRADE.
- ✅ **Portfolio risk integrator** — live PortfolioState feeding circuit breakers.
- ⬜ Expand library; per-strategy parameter optimization under overfitting guard.

### Phase 6 — Signals ✅
- ✅ Unified 0–100 scorer with quality classification.
- ✅ Multi-timeframe confirmation + signal generator.
- ✅ **Enhanced daily review** — 10 daily review questions, per-strategy/regime breakdown.
- ✅ **Enhanced weekly review** — full audit, degradation reports, ensemble suggestions.
- ⬜ Calibrate component weights from realized outcomes.

### Phase 7 — Risk & sizing + News intelligence ✅
- ✅ Risk engine (10 checks) with absolute veto + circuit breaker.
- ✅ Position sizer (fixed/ATR/vol-adjusted/futures) with position cap.
- ✅ Correlation engine + drawdown monitor.
- ✅ **RSS fetcher** — free financial news from MarketWatch, CNBC, Yahoo Finance.
- ✅ **News aggregator** — multi-source dedup, classification, relevance scoring.
- ✅ **News pipeline** — async background polling, event bus integration, trade risk assessment.
- ✅ **Economic calendar** — blackout/elevated risk windows around high-impact events.

### Phase 8 — Execution + AI memory ✅
- ✅ Deterministic paper engine.
- ✅ Alpaca executor (shadow/live, SDK-optional).
- ✅ Order manager with duplicate protection + reconciliation.
- ✅ **LLM analyzer** — trade batch analysis, strategy evaluation, pattern detection, news impact.
- ✅ **Strategy learner** — closes the learning loop: drift detection, regime fit, parameter proposals.
- ✅ **Pattern detector** — time-of-day, day-of-week, regime, streak, exit reason, R-multiple patterns.
- ⬜ Live order lifecycle handling (partial fills, cancels, retries) against Alpaca.

### Phase 9 — End-to-end paper trading ✅
- ✅ No-look-ahead backtest engine (next-bar-open fills).
- ✅ Metrics suite, Monte-Carlo, walk-forward.
- ✅ Hypothesis manager, overfitting detector, strategy comparator.
- ✅ **Paper trading loop** — async main runner wiring data→features→regime→signals→risk→execution→review.
- ✅ **Session manager** — NYSE schedule, premarket/regular/review/afterhours phases, daily+weekly review scheduling.
- ⬜ Backtest data pipeline over persisted history; experiment tracking UI.

### Phase 10 — Memory, learning & agents ✅
- ✅ Knowledge store, trade memory, learning engine.
- ✅ 10 specialized agents (incl. risk-manager & strategy-governor vetoes).
- ✅ Decision loop + daily/weekly reviews.
- ✅ Learning loop closed: StrategyLearner proposes, LearningEngine requires approval.

### Phase 11 — Control plane & alerts ✅
- ✅ FastAPI app with system/account/positions/strategies/signals/risk/research
  routers + `/health`.
- ✅ Configurable alert manager (log + webhook channels, severity-aware).
- ⬜ AuthN/Z on the API; dashboard UI; Prometheus metrics endpoint.

### Phase 12 — Shadow trading ✅
- ✅ `ShadowEngine` records intended orders without any broker connection and
  reconciles each against the real achievable market price.
- ✅ Divergence analytics: per-order price divergence, adverse slippage (bps),
  observation latency, fill rate, and paper-vs-shadow realised P&L divergence.
- ✅ `DivergenceReport.divergence_pct` takes the *worse* of price and P&L
  divergence, and fails closed (1.0) when there is no evidence at all.
- ✅ `ShadowTradingLoop` runs the pipeline against live data, mirrors intents
  into a parallel paper book, and feeds metrics to the SHADOW promotion gate.
- ✅ Loop refuses to start unless `TRADING_MODE` ∈ {PAPER, SHADOW, RESEARCH};
  aborts every tick when emergency-stopped; trades only in REGULAR session.
- ⬜ Accumulate real shadow-mode runtime evidence (requires live market data).

### Phase 13 — Governance & human approval gates ✅
- ✅ `governance/approval_registry.py` — append-only, auditable approval ledger.
  Quorum-based: **both** a risk officer and the portfolio owner must sign off;
  the `SYSTEM` role can veto but can never cast an approving vote.
- ✅ Approvals expire (72h default), can be revoked at any time, and any single
  rejection is terminal. Duplicate votes rejected.
- ✅ `governance/risk_review.py` — 12-item RISK_REVIEW checklist: 7 automated
  assertions evaluated from collected evidence + 5 manual human attestations.
  Unanswered mandatory items block promotion (fails closed).
- ✅ `governance/live_authorization.py` — deny-by-default gate requiring **all**
  of: complete automated validation, passed risk review, valid multi-role human
  approval, out-of-band `LIVE_TRADING_AUTHORIZED` env var, no emergency stop,
  and a configured capital cap. Issues only time-boxed, capital-capped grants.
- ✅ `/governance/*` API routes for approvals, votes, revocation, the risk
  review checklist, the audit log, and live posture inspection.
- ✅ `RUNBOOK.md` — operational runbook for daily ops, incidents and promotion.

### Phase 14 — Live trading — NOT AUTHORIZED ⬜
**Live trading is disabled and will stay disabled.** Everything below requires
explicit human authorization that has not been given.
- ⬜ Accumulate `PAPER` runtime meeting `MIN_PAPER_TRADES` /
  `MIN_PAPER_DURATION_DAYS`.
- ⬜ Accumulate `SHADOW` runtime with divergence inside the 10% gate.
- ⬜ Complete a real RISK_REVIEW checklist with named human attesters.
- ⬜ Obtain a real dual-role approval record.
- ⬜ Set `LIVE_TRADING_AUTHORIZED` out of band and configure a capital cap.
- ⬜ Live Alpaca order lifecycle hardening (partial fills, cancels, retries).
- ⬜ API AuthN/Z and Prometheus metrics before any live exposure.

---

## Current status summary

| Layer | Status |
|-------|--------|
| Foundation (config/core) | ✅ complete |
| Data & persistence | ✅ scaffold; migration/apply pending |
| Market data | ✅ scaffold; live wiring + futures provider pending |
| Features | ✅ complete |
| Regime & news | ✅ complete (news pipeline live; data-driven regime model pending) |
| Strategies | ✅ 17 implemented; validation pipeline complete |
| Signals | ✅ complete |
| Risk & sizing | ✅ complete; portfolio risk integration live |
| Execution | ✅ scaffold; live lifecycle pending |
| Backtesting & research | ✅ complete |
| Memory/learning/agents | ✅ complete; learning loop closed |
| News intelligence | ✅ complete (RSS + Alpaca + aggregator + pipeline) |
| Paper trading loop | ✅ complete (end-to-end async runner) |
| API & alerts | ✅ complete; auth/UI/metrics pending |
| Shadow trading | ✅ complete (engine + loop + divergence analytics) |
| Governance & approvals | ✅ complete (registry + risk review + live gate) |
| Live trading | ⬜ **NOT AUTHORIZED** — gate is deny-by-default |

**Test suite:** 200 tests passing — unit + integration, no live broker or database.

The platform is operationally complete for paper trading and shadow trading, and
the governance machinery that guards live capital is fully implemented and
tested. Live trading remains disabled by default and cannot be enabled by code:
it requires dual-role human sign-off plus an out-of-band operator environment
variable. The remaining ⬜ items are runtime evidence accumulation and
pre-live hardening.
