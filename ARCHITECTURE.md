# Architecture

This document describes the design of the **Autonomous Adaptive Trading
Intelligence Platform**: its layers, data flow, data model, agent architecture,
promotion pipeline, risk architecture, Alpaca integration plan (including the
futures gap), security model and the rationale behind the key technology
choices.

---

## 1. Design goals & non-negotiables

1. **Capital preservation first.** Every trade passes an authoritative risk
   engine that can veto it. A circuit breaker and a global kill switch stop
   trading instantly.
2. **No unsafe automation.** The system defaults to `PAPER` and is promoted to
   live capital only by a human, one gated step at a time.
3. **Truthful data.** The platform never fabricates prices, fills, or broker
   capabilities. When data or the broker SDK is unavailable, code paths fail
   *soft* (no trade) rather than inventing a result.
4. **Modularity.** Each concern (data, features, regime, strategies, signals,
   risk, execution, research, memory, agents, orchestration, API) is an
   independent, testable package.
5. **Observability & auditability.** Structured logging everywhere; every mode
   transition and risk decision is recorded.
6. **Adaptivity.** A research/memory/learning loop continuously evaluates and
   improves strategies without ever bypassing risk controls.

---

## 2. Layered architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│  Presentation / control     api/ (FastAPI) · alerts/                   │
├──────────────────────────────────────────────────────────────────────┤
│  Orchestration              orchestration/ · agents/                   │
├──────────────────────────────────────────────────────────────────────┤
│  Decision                   signals/ · risk/ · execution/             │
├──────────────────────────────────────────────────────────────────────┤
│  Intelligence               strategies/ · regime/ · news/ ·           │
│                             research/ · memory/ · backtesting/         │
├──────────────────────────────────────────────────────────────────────┤
│  Feature                    features/                                  │
├──────────────────────────────────────────────────────────────────────┤
│  Data                       market_data/ · database/                  │
├──────────────────────────────────────────────────────────────────────┤
│  Foundation                 config/ · core/                           │
└──────────────────────────────────────────────────────────────────────┘
```

Lower layers never import upper layers. The **foundation** layer (`config`,
`core`) is dependency-free of the rest and is imported everywhere.

---

## 3. Foundation layer

### 3.1 `config/`
- **`settings.py`** — Pydantic `BaseSettings` (`Settings`) with a cached
  singleton `get_settings()`. Holds environment metadata, Alpaca credentials
  (resolved lazily, env → secrets file), infrastructure URLs, the `TradingMode`
  enum, **all risk parameters**, signal thresholds, promotion gates, backtest
  cost model and logging config. `resolve_alpaca_credentials()` reads the
  platform secrets file case-insensitively; nothing is hardcoded.
- **`constants.py`** — enumerations and immutable domain constants:
  `AssetClass`, `Timeframe` (with `.seconds`), `MarketRegime` (10 regimes),
  `StrategyStatus`, `SignalDirection`, `OrderType/Side/Status`, `DataQuality`,
  `EventTopic`, the **`FUTURES_SPECS`** table (MES/MNQ/MYM/M2K) and default
  universes.
- **`logging_config.py`** — `configure_logging()` sets up `structlog` (JSON or
  console); `get_logger()` returns a bound logger.

### 3.2 `core/`
- **`system_state.py`** — a thread-safe **singleton state machine**. Enforces
  the legal transition graph, exposes `is_trading_allowed()`, the
  `engage_emergency_stop()` / `reset_emergency_stop()` kill switch, and keeps an
  audit `history` of `StateTransition` records. Illegal transitions raise
  `IllegalTransitionError`.
- **`event_bus.py`** — a lightweight async publish/subscribe bus keyed by
  `EventTopic` for decoupled inter-module communication.
- **`clock.py`** — `MarketClock` and `utc_now()`; centralizes time so tests and
  backtests are deterministic.

---

## 4. Data flow (end-to-end)

```
                    ┌─────────────────────────────────────────────┐
                    │              config / core                    │
                    └─────────────────────────────────────────────┘
                                      ▲ (settings, state, clock)
 (1) INGEST                          │
 Alpaca REST/stream ──▶ market_data.alpaca_client ─┐
 Futures provider  ──▶ market_data.historical  ────┤
                                                    ▼
 (2) VALIDATE   market_data.data_validator  ──▶ DataQuality {CLEAN|WARNING|CORRUPTED}
                    (CORRUPTED ⇒ dropped; never traded on)
                                                    ▼
 (3) PERSIST    database.repositories ──▶ PostgreSQL (OHLCV, assets, …)
                                                    ▼
 (4) FEATURES   features.feature_engine ──▶ FeatureResult (trend/momentum/vol/…)
                                                    ▼
 (5) REGIME     regime.classifier ──▶ RegimeResult      news.* ──▶ news environment
                                                    ▼
 (6) STRATEGY   strategies.* (17) ──▶ StrategySignal (validated, R:R checked)
                                                    ▼
 (7) SCORE      signals.signal_scorer (0–100) + signals.multi_timeframe
                    (below threshold ⇒ rejected)
                                                    ▼
 (8) RISK       risk.risk_engine.check_trade() ── veto? ──▶ (rejected + logged)
                    │ approved                          ▲
                    ▼                                   │ kill switch / circuit breaker
 (9) SIZE       risk.position_sizer ──▶ SizingResult
                                                    ▼
 (10) EXECUTE   execution.order_manager ──▶ paper | shadow | live
                                                    ▼
 (11) RECORD    database (orders, trades) + memory.trade_memory
                                                    ▼
 (12) LEARN     memory.learning_engine + research.* ──▶ improve strategies
                    (loop back to 6 via orchestration.decision_loop)
```

Every arrow that could produce a trade is gated by steps (2), (7) and (8). No
step invents data: a missing input yields *no signal* / *no trade*.

---

## 5. Data layer (`database/`)

- **`models.py`** — 26 SQLAlchemy 2.0 (`DeclarativeBase`) models, each with a
  UUID primary key and `created_at` / `updated_at` timestamps, plus indexes on
  hot columns. Domains covered: assets & instruments, OHLCV bars, strategies &
  versions, signals, orders, trades & fills, positions, risk events, regime
  history, news events, hypotheses & experiments, knowledge/memory records,
  agent decisions, and audit logs. `ALL_MODELS` enumerates them.
- **`session.py`** — engine/session factory, `session_scope()` context manager,
  `get_db()` dependency for FastAPI, and `init_db()`.
- **`repositories/`** — a `BaseRepository` plus typed repositories (assets,
  market data, strategies, signals, orders, trades, knowledge) encapsulating all
  queries so the rest of the code never writes raw SQL.
- **`migrations/`** — Alembic environment (`env.py`) that pulls the URL from
  settings and the metadata from `models.Base`, keeping schema and code in sync.

### 5.1 Entity relationships (simplified ERD)

```
Asset 1───∞ OHLCVBar
Asset 1───∞ Signal ∞───1 Strategy 1───∞ StrategyVersion
Signal 1───∞ Order 1───∞ Fill
Order  ∞───1 Strategy
Trade  ∞───1 Strategy        Trade 1───∞ Fill
Position ∞───1 Asset
RiskEvent ∞───1 (Order|Trade)
RegimeSnapshot ∞───1 Asset
NewsEvent ∞───∞ Asset
Hypothesis 1───∞ Experiment
KnowledgeRecord / TradeMemory  (learning)
AgentDecision  (audit of agent outputs)
AuditLog  (mode transitions, kill switch, risk vetoes)
```

---

## 6. Market data & the futures gap (`market_data/`)

- **`alpaca_client.py`** — thin wrapper over `alpaca-py`. **SDK-optional**: the
  import is guarded by an `_ALPACA_SDK` flag and every method checks
  `sdk_available`, so the module imports and the platform runs even without the
  SDK or credentials. Includes retry/backoff.
- **`data_validator.py`** — detects empty frames, missing columns, null/
  non-positive prices, OHLC inconsistencies, duplicate/out-of-order timestamps,
  extreme jumps and volume anomalies. Returns a `ValidationReport`;
  `CORRUPTED` data is never tradable.
- **`historical.py`** — `HistoricalDataService` plus the **`FuturesDataProvider`
  ABC**. Alpaca serves **no futures**, so futures data must come from a
  pluggable provider implementation; the platform refuses to fabricate it.
- **`stream_manager.py`** — real-time subscription management.
- **`asset_universe.py`** — the tradable universe (equities/ETFs/crypto + futures
  specs).

---

## 7. Feature layer (`features/`)

All indicators are **implemented from scratch** (no TA-Lib dependency):

- `trend.py` — SMA, EMA, WMA, VWAP, MACD, ADX.
- `momentum.py` — RSI (Wilder), Stochastic, Williams %R, ROC, CCI.
- `volatility.py` — True Range, ATR, historical volatility, Bollinger Bands,
  Keltner Channels, volatility percentile.
- `volume.py`, `price_structure.py`, `market_profile.py`, `fair_value.py`.
- `feature_engine.py` — the `FeatureEngine` orchestrates all indicator families
  into a single `FeatureResult` used downstream.

Every indicator honors `min_periods`, returning `NaN` (not garbage) until enough
history exists — preventing premature signals.

---

## 8. Intelligence layer

### 8.1 Regime (`regime/`)
`RegimeClassifier` maps features to one of 10 `MarketRegime` states (trending
up/down, ranging, volatile, quiet, breakout, reversal, etc.). `regime_history.py`
tracks transitions; strategies declare which regimes they are `allowed_regimes`.

### 8.2 News (`news/`)
`news_fetcher.py`, `news_classifier.py` and `economic_calendar.py` produce a
"news environment" that can suppress or contextualize signals (e.g. avoid new
entries around high-impact events).

### 8.3 Strategies (`strategies/`)
- `base_strategy.py` — the `BaseStrategy` ABC and the `StrategySignal`
  dataclass. Signals are **self-validating**: required fields must be present and
  the stop/entry/target must be on the correct side for the direction, else a
  `SignalValidationError` is raised. No partial signals ever propagate.
- **17 strategies** across five families: `trend/` (×4), `momentum/` (×4),
  `mean_reversion/` (×4), `breakout/` (×4) and `cross_market/`
  (SPY/QQQ relationship). Each returns a fully-formed signal or `None`.

### 8.4 Research (`research/`)
`hypothesis_manager.py` (IDs like `HYP-YYYY-NNNNNN`), `overfitting_detector.py`
(guards against curve-fitting), and `strategy_comparator.py`.

### 8.5 Memory & learning (`memory/`)
`knowledge_store.py`, `trade_memory.py` and `learning_engine.py` capture
outcomes and feed strategy improvement — always subordinate to risk controls.

### 8.6 Backtesting (`backtesting/`)
- `backtest_engine.py` — **no look-ahead**: signals generated on bar *i* are
  filled at the **open of bar i+1**; stops/targets checked intrabar. Configurable
  commission and slippage models.
- `metrics.py` — total/annualized return, Sharpe, Sortino, max drawdown, CVaR,
  win rate, profit factor, expectancy, etc.
- `monte_carlo.py` — resampling for confidence intervals.
- `walk_forward.py` — rolling in-sample/out-of-sample validation.

---

## 9. Decision layer

### 9.1 Signals (`signals/`)
`signal_scorer.py` produces a unified **0–100** score from weighted components
and classifies it as `REJECTED` / `QUALIFIED` / `HIGH_QUALITY` against
configurable thresholds. `multi_timeframe.py` requires higher-timeframe
confirmation. `signal_generator.py` ties strategies + scoring together.

### 9.2 Risk (`risk/`)
The **authoritative** layer. `risk_engine.py::check_trade()` runs, in order:
trading-allowed check, circuit-breaker check, then max risk per trade → position
size → simultaneous trades → leverage → correlated exposure → daily loss →
weekly loss → portfolio drawdown. Any failure returns
`RiskDecision(allowed=False, reason=…)` with a full audit of the checks.
`circuit_breaker_check()` trips the global emergency stop on a hard loss breach.
`position_sizer.py` supports fixed-fractional, ATR-based, volatility-adjusted and
**futures-contract** sizing (using `FUTURES_SPECS`), always capped by
`MAX_POSITION_SIZE_PCT`. `correlation_engine.py` and `drawdown_monitor.py`
support the cluster and drawdown checks.

### 9.3 Execution (`execution/`)
- `paper_engine.py` — deterministic simulated fills (paper mode).
- `alpaca_executor.py` — routes to Alpaca; **shadow** logs only, **live**
  submits (SDK required; fails soft if unavailable).
- `order_manager.py` — mode-aware routing, duplicate-order protection
  (`DuplicateOrderError`) and reconciliation.

---

## 10. Agent architecture (`agents/`)

Ten specialized agents, each subclassing `BaseAgent` and returning an
`AgentDecision`:

| Agent | Responsibility | Special power |
|-------|----------------|---------------|
| `market_scanner` | Scan universe for candidates | — |
| `regime_analyst` | Determine current regime | — |
| `news_analyst` | Assess news environment | — |
| `quant_researcher` | Propose/refine hypotheses | — |
| `backtesting_agent` | Validate ideas historically | — |
| `risk_manager` | Enforce risk limits | **veto** |
| `execution_agent` | Place & manage orders | — |
| `trade_reviewer` | Post-trade analysis | — |
| `learning_agent` | Update memory/knowledge | — |
| `strategy_governor` | Approve strategy status/promotion | **veto** |

The `risk_manager` and `strategy_governor` hold veto authority; no agent can
override the risk engine or the kill switch.

### 10.1 Orchestration (`orchestration/`)
`decision_loop.py` sequences the agents into a `LoopDecision` per cycle;
`daily_review.py` and `weekly_review.py` run scheduled reviews that feed the
learning loop.

---

## 11. Trading modes & promotion pipeline

Legal transitions (enforced by `core/system_state.py`):

```
DISABLED  → {RESEARCH, BACKTEST, PAPER}
RESEARCH  → {BACKTEST, PAPER, DISABLED}
BACKTEST  → {RESEARCH, PAPER, DISABLED}
PAPER     → {RESEARCH, BACKTEST, SHADOW, DISABLED}
SHADOW    → {PAPER, LIVE, DISABLED}
LIVE      → {SHADOW, PAPER}
EMERGENCY_STOP → {DISABLED}         (manual reset only)
```

Key properties:
- **`PAPER → LIVE` is impossible** — you must pass through `SHADOW`.
- **`DISABLED → SHADOW/LIVE` is impossible** — you must build up through paper.
- Promotion gates (`MIN_PAPER_TRADES`, `MIN_PAPER_DURATION_DAYS`) provide the
  evidentiary bar before promotion is even considered.
- `EMERGENCY_STOP` can be entered from anywhere and only reset to `DISABLED` by
  a human.

---

## 12. Risk architecture

```
                       ┌───────────────────────────────┐
  Signal ──────────────▶  RiskEngine.check_trade()      │
                       │  1. trading allowed?           │──▶ veto
                       │  2. circuit breaker active?    │──▶ veto
                       │  3. max risk / trade           │──▶ veto
                       │  4. max position size          │──▶ veto
                       │  5. max simultaneous trades    │──▶ veto
                       │  6. max leverage               │──▶ veto
                       │  7. max correlated exposure    │──▶ veto
                       │  8. daily loss limit           │──▶ veto
                       │  9. weekly loss limit          │──▶ veto
                       │ 10. portfolio drawdown         │──▶ veto
                       └───────────────┬───────────────┘
                                       │ all pass
                                       ▼
                               PositionSizer  ──▶ Order
                                       ▲
        Circuit breaker (hard loss)  ──┘ trips ──▶ SystemState.emergency_stop()
                                                     (halts all layers)
```

All thresholds live in `settings.py`. The engine returns a structured
`RiskDecision` with the per-check audit trail, which is logged and persisted.

---

## 13. Alpaca integration plan

- **Auth:** credentials resolved from env or the platform secrets file
  (case-insensitive); base URL defaults to the **paper** endpoint.
- **SDK-optional:** all Alpaca modules guard the `alpaca-py` import and check
  `sdk_available`. Without the SDK the platform still imports, backtests, and
  runs in paper mode; live routing simply reports `alpaca_sdk_unavailable`
  instead of inventing a fill.
- **Data:** REST for historical bars, websocket streaming for real-time.
- **Execution:** market/limit orders via the trading client in `LIVE`; `SHADOW`
  logs the intended order only.
- **Assets:** US equities/ETFs and crypto are supported by Alpaca.
- **Futures gap:** Alpaca provides **no** futures data or execution. Futures
  (MES/MNQ/MYM/M2K) are therefore abstracted behind `FuturesDataProvider`, and a
  concrete provider/broker must be supplied before futures trading is possible.
  The platform will not fabricate futures data or fills.

---

## 14. Security & safety model

- **Secrets:** never hardcoded; `.env` and secrets files are git-ignored;
  resolution falls back to the platform secrets store.
- **Least privilege:** the API exposes monitoring and explicit human-in-the-loop
  controls (mode change, kill switch), not implicit trade origination.
- **Fail-safe defaults:** `PAPER` mode, cash-only leverage (`MAX_LEVERAGE=1.0`),
  conservative loss limits out of the box.
- **Auditability:** structured logs + persisted `StateTransition`, risk events
  and agent decisions.
- **Containerization:** Docker image runs as a non-root user with a health
  check; live trading is never enabled implicitly by the container.

---

## 15. Technology choices & rationale

| Choice | Why |
|--------|-----|
| **Python 3.11+** | Rich quant/ML ecosystem; performance improvements; modern typing. |
| **Pydantic v2 / pydantic-settings** | Typed, validated config from env with zero boilerplate. |
| **SQLAlchemy 2.0 + Alembic** | Mature ORM with typed models and versioned migrations. |
| **PostgreSQL** | Reliable relational store for time series + relational domain data. |
| **Redis** | Fast cache / pub-sub for streaming and coordination. |
| **FastAPI + Uvicorn** | Async, typed, self-documenting control plane. |
| **structlog** | Structured, queryable logs essential for auditing a trading system. |
| **NumPy / Pandas / SciPy / scikit-learn** | Vectorized indicators, stats and ML for regime/research/learning. |
| **alpaca-py** | Official broker SDK; wrapped and kept optional to avoid hard coupling. |
| **From-scratch indicators** | No native/TA-Lib build dependency; full transparency and testability. |
| **Docker Compose** | One-command reproducible local stack. |

---

## 16. Testing strategy

Unit tests target pure, deterministic logic (indicators with known values, risk
vetoes, sizing incl. futures, kill switch/mode transitions, signal scoring, data
validation, order routing) and an integration test exercises the backtest engine
end-to-end on synthetic data. Tests require **no** live broker or database, so
they run anywhere and gate every change.

See [`ROADMAP.md`](ROADMAP.md) for how these pieces are phased and what remains.
