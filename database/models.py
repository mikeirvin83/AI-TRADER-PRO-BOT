"""SQLAlchemy ORM models — complete platform schema.

Design principles
-----------------
* Every table has a UUID primary key (``id``) plus ``created_at`` / ``updated_at``.
* Indexes are declared on the hot query columns: ``symbol``, ``timestamp``,
  ``strategy_id``.
* ``market_data`` is designed to be partitioned by (symbol, timeframe) and
  time-ranged in PostgreSQL. See the class comment for the partitioning strategy.
* Money/price columns use ``Numeric`` for exactness; ratios/scores use ``Float``.
* No business logic lives here — models are pure persistence.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _uuid() -> uuid.UUID:
    return uuid.uuid4()


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    """Declarative base with common id/timestamp columns for every table."""

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=_uuid
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_now, onupdate=_now, nullable=False
    )


# --------------------------------------------------------------------------- #
# Reference / account
# --------------------------------------------------------------------------- #
class User(Base):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    role: Mapped[str] = mapped_column(String(50), default="operator")


class Asset(Base):
    __tablename__ = "assets"
    __table_args__ = (Index("ix_assets_symbol", "symbol"),)

    symbol: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), default="")
    asset_class: Mapped[str] = mapped_column(String(20), nullable=False)  # EQUITY/CRYPTO/FUTURE...
    exchange: Mapped[str] = mapped_column(String(32), default="")
    tradable: Mapped[bool] = mapped_column(Boolean, default=True)
    shortable: Mapped[bool] = mapped_column(Boolean, default=False)
    # Futures-specific (nullable for non-futures)
    tick_size: Mapped[float | None] = mapped_column(Float, nullable=True)
    tick_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    contract_multiplier: Mapped[float | None] = mapped_column(Float, nullable=True)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)


# --------------------------------------------------------------------------- #
# Market data
# --------------------------------------------------------------------------- #
class MarketData(Base):
    """OHLCV bars.

    Partitioning strategy (PostgreSQL): declarative partitioning by RANGE on
    ``timestamp`` (monthly partitions), sub-partitioned or heavily indexed by
    (symbol, timeframe). For very high-frequency data, use TimescaleDB hypertables
    on this table. The unique constraint below guarantees idempotent upserts.
    """

    __tablename__ = "market_data"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_bar"),
        Index("ix_md_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
        Index("ix_md_timestamp", "timestamp"),
    )

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    open: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    high: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    low: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    close: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    volume: Mapped[float] = mapped_column(Numeric(24, 4), nullable=False, default=0)
    vwap: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    trade_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    is_adjusted: Mapped[bool] = mapped_column(Boolean, default=False)
    is_estimated: Mapped[bool] = mapped_column(Boolean, default=False)  # gap-fill flag
    data_quality: Mapped[str] = mapped_column(String(12), default="CLEAN")


class News(Base):
    __tablename__ = "news"
    __table_args__ = (Index("ix_news_symbol_ts", "symbol", "published_at"),)

    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    headline: Mapped[str] = mapped_column(Text, nullable=False)
    summary: Mapped[str] = mapped_column(Text, default="")
    source: Mapped[str] = mapped_column(String(128), default="")
    url: Mapped[str] = mapped_column(Text, default="")
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    sentiment: Mapped[str | None] = mapped_column(String(16), nullable=True)  # bullish/bearish/neutral
    sentiment_score: Mapped[float | None] = mapped_column(Float, nullable=True)  # -1..1
    impact: Mapped[str | None] = mapped_column(String(16), nullable=True)  # low/medium/high
    raw: Mapped[dict] = mapped_column(JSONB, default=dict)


class EconomicEvent(Base):
    __tablename__ = "economic_events"
    __table_args__ = (Index("ix_econ_ts", "event_time"),)

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    country: Mapped[str] = mapped_column(String(8), default="US")
    event_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    importance: Mapped[str] = mapped_column(String(16), default="medium")  # low/medium/high
    actual: Mapped[str | None] = mapped_column(String(64), nullable=True)
    forecast: Mapped[str | None] = mapped_column(String(64), nullable=True)
    previous: Mapped[str | None] = mapped_column(String(64), nullable=True)
    risk_state: Mapped[str] = mapped_column(String(16), default="normal")  # normal/elevated/blackout


# --------------------------------------------------------------------------- #
# Features
# --------------------------------------------------------------------------- #
class Feature(Base):
    __tablename__ = "features"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_feature"),
        Index("ix_feat_symbol_tf_ts", "symbol", "timeframe", "timestamp"),
    )

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    values: Mapped[dict] = mapped_column(JSONB, default=dict)  # {feature_name: value}


# --------------------------------------------------------------------------- #
# Strategies & versions
# --------------------------------------------------------------------------- #
class Strategy(Base):
    __tablename__ = "strategies"
    __table_args__ = (Index("ix_strategies_name", "name"),)

    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(32), default="")  # trend/momentum/...
    status: Mapped[str] = mapped_column(String(20), default="UNDER_RESEARCH")
    description: Mapped[str] = mapped_column(Text, default="")
    allowed_regimes: Mapped[list] = mapped_column(JSONB, default=list)
    min_signal_score: Mapped[int] = mapped_column(Integer, default=75)
    current_version: Mapped[str] = mapped_column(String(20), default="0.1.0")
    params: Mapped[dict] = mapped_column(JSONB, default=dict)

    versions: Mapped[list["StrategyVersion"]] = relationship(back_populates="strategy")


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"
    __table_args__ = (
        UniqueConstraint("strategy_id", "version", name="uq_strategy_version"),
        Index("ix_sv_strategy", "strategy_id"),
    )

    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    params: Mapped[dict] = mapped_column(JSONB, default=dict)
    code_hash: Mapped[str] = mapped_column(String(64), default="")
    notes: Mapped[str] = mapped_column(Text, default="")

    strategy: Mapped["Strategy"] = relationship(back_populates="versions")


class StrategyTest(Base):
    __tablename__ = "strategy_tests"
    __table_args__ = (Index("ix_st_strategy", "strategy_id"),)

    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    test_type: Mapped[str] = mapped_column(String(32), nullable=False)  # backtest/oos/wf/mc/paper/shadow
    passed: Mapped[bool] = mapped_column(Boolean, default=False)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


# --------------------------------------------------------------------------- #
# Backtests & validation
# --------------------------------------------------------------------------- #
class Backtest(Base):
    __tablename__ = "backtests"
    __table_args__ = (Index("ix_bt_strategy", "strategy_id"),)

    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    start_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    initial_capital: Mapped[float] = mapped_column(Numeric(20, 2), default=100000)
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    equity_curve: Mapped[list] = mapped_column(JSONB, default=list)
    params: Mapped[dict] = mapped_column(JSONB, default=dict)


class WalkForwardTest(Base):
    __tablename__ = "walk_forward_tests"
    __table_args__ = (Index("ix_wf_strategy", "strategy_id"),)

    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    windows: Mapped[list] = mapped_column(JSONB, default=list)  # per-window metrics
    aggregate_metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    efficiency: Mapped[float | None] = mapped_column(Float, nullable=True)  # OOS/IS ratio


class MonteCarloTest(Base):
    __tablename__ = "monte_carlo_tests"
    __table_args__ = (Index("ix_mc_strategy", "strategy_id"),)

    strategy_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("strategies.id"), nullable=False)
    n_simulations: Mapped[int] = mapped_column(Integer, default=10000)
    median_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    p5_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    p95_return: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_drawdown_p95: Mapped[float | None] = mapped_column(Float, nullable=True)
    probability_of_ruin: Mapped[float | None] = mapped_column(Float, nullable=True)
    distribution: Mapped[dict] = mapped_column(JSONB, default=dict)


# --------------------------------------------------------------------------- #
# Signals, orders, fills, positions, trades
# --------------------------------------------------------------------------- #
class Signal(Base):
    __tablename__ = "signals"
    __table_args__ = (
        Index("ix_signals_symbol_ts", "symbol", "created_at"),
        Index("ix_signals_strategy", "strategy_id"),
    )

    strategy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategies.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)  # LONG/SHORT/FLAT
    entry_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    stop_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    target_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    score: Mapped[float] = mapped_column(Float, default=0.0)  # 0-100
    regime: Mapped[str | None] = mapped_column(String(24), nullable=True)
    news_environment: Mapped[str | None] = mapped_column(String(24), nullable=True)
    invalidation_condition: Mapped[str] = mapped_column(Text, nullable=False)
    expiration_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), default="")
    rationale: Mapped[dict] = mapped_column(JSONB, default=dict)
    acted_on: Mapped[bool] = mapped_column(Boolean, default=False)


class Order(Base):
    __tablename__ = "orders"
    __table_args__ = (
        Index("ix_orders_symbol", "symbol"),
        Index("ix_orders_strategy", "strategy_id"),
        Index("ix_orders_broker_id", "broker_order_id"),
    )

    signal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    strategy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategies.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    order_type: Mapped[str] = mapped_column(String(16), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    limit_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    time_in_force: Mapped[str] = mapped_column(String(8), default="day")
    status: Mapped[str] = mapped_column(String(20), default="PENDING")
    mode: Mapped[str] = mapped_column(String(12), default="PAPER")  # PAPER/SHADOW/LIVE
    broker_order_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    client_order_id: Mapped[str] = mapped_column(String(64), default="")
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    filled_qty: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    avg_fill_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    reject_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    fills: Mapped[list["Fill"]] = relationship(back_populates="order")


class Fill(Base):
    __tablename__ = "fills"
    __table_args__ = (Index("ix_fills_order", "order_id"),)

    order_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("orders.id"), nullable=False)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    side: Mapped[str] = mapped_column(String(8), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    commission: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    slippage: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    filled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    order: Mapped["Order"] = relationship(back_populates="fills")


class Position(Base):
    __tablename__ = "positions"
    __table_args__ = (Index("ix_positions_symbol", "symbol"),)

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    avg_entry_price: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    current_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    market_value: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    unrealized_pnl: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    realized_pnl: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    mode: Mapped[str] = mapped_column(String(12), default="PAPER")
    is_open: Mapped[bool] = mapped_column(Boolean, default=True)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Trade(Base):
    """A completed round-trip trade with full context for post-trade review."""

    __tablename__ = "trades"
    __table_args__ = (
        Index("ix_trades_symbol", "symbol"),
        Index("ix_trades_strategy", "strategy_id"),
    )

    strategy_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("strategies.id"), nullable=True)
    signal_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("signals.id"), nullable=True)
    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    entry_price: Mapped[float] = mapped_column(Numeric(20, 8), nullable=False)
    exit_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    stop_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    target_price: Mapped[float | None] = mapped_column(Numeric(20, 8), nullable=True)
    entry_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    exit_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pnl: Mapped[float | None] = mapped_column(Numeric(20, 2), nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)
    r_multiple: Mapped[float | None] = mapped_column(Float, nullable=True)
    mae: Mapped[float | None] = mapped_column(Float, nullable=True)  # max adverse excursion
    mfe: Mapped[float | None] = mapped_column(Float, nullable=True)  # max favourable excursion
    commission: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    slippage: Mapped[float] = mapped_column(Numeric(20, 8), default=0)
    regime: Mapped[str | None] = mapped_column(String(24), nullable=True)
    news_environment: Mapped[str | None] = mapped_column(String(24), nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    mode: Mapped[str] = mapped_column(String(12), default="PAPER")
    context: Mapped[dict] = mapped_column(JSONB, default=dict)


class PortfolioSnapshot(Base):
    __tablename__ = "portfolio_snapshots"
    __table_args__ = (Index("ix_snap_ts", "snapshot_time"),)

    snapshot_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    equity: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    cash: Mapped[float] = mapped_column(Numeric(20, 2), nullable=False)
    long_market_value: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    short_market_value: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    unrealized_pnl: Mapped[float] = mapped_column(Numeric(20, 2), default=0)
    drawdown_pct: Mapped[float] = mapped_column(Float, default=0.0)
    open_positions: Mapped[int] = mapped_column(Integer, default=0)
    mode: Mapped[str] = mapped_column(String(12), default="PAPER")


# --------------------------------------------------------------------------- #
# Regime, research, memory, learning
# --------------------------------------------------------------------------- #
class MarketRegimeRow(Base):
    __tablename__ = "market_regimes"
    __table_args__ = (Index("ix_regime_symbol_ts", "symbol", "timestamp"),)

    symbol: Mapped[str] = mapped_column(String(32), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), default="1Day")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    regime: Mapped[str] = mapped_column(String(24), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    features: Mapped[dict] = mapped_column(JSONB, default=dict)


class ResearchHypothesis(Base):
    __tablename__ = "research_hypotheses"
    __table_args__ = (
        UniqueConstraint("hyp_id", name="uq_hyp_id"),
        Index("ix_hyp_status", "status"),
    )

    hyp_id: Mapped[str] = mapped_column(String(20), nullable=False)  # HYP-YYYY-NNNNNN
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    rationale: Mapped[str] = mapped_column(Text, default="")
    proposed_by: Mapped[str] = mapped_column(String(64), default="quant_researcher")
    status: Mapped[str] = mapped_column(String(16), default="PROPOSED")
    success_criteria: Mapped[dict] = mapped_column(JSONB, default=dict)
    results: Mapped[dict] = mapped_column(JSONB, default=dict)


class KnowledgeMemory(Base):
    __tablename__ = "knowledge_memory"
    __table_args__ = (Index("ix_km_key", "key"),)

    key: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(64), default="general")
    content: Mapped[dict] = mapped_column(JSONB, default=dict)
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    evidence_count: Mapped[int] = mapped_column(Integer, default=0)
    last_reinforced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class LearningEvent(Base):
    __tablename__ = "learning_events"
    __table_args__ = (Index("ix_le_ts", "created_at"),)

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    before_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    after_state: Mapped[dict] = mapped_column(JSONB, default=dict)
    approved: Mapped[bool] = mapped_column(Boolean, default=False)
    approved_by: Mapped[str | None] = mapped_column(String(64), nullable=True)


# --------------------------------------------------------------------------- #
# Risk, system, models
# --------------------------------------------------------------------------- #
class RiskEvent(Base):
    __tablename__ = "risk_events"
    __table_args__ = (Index("ix_risk_ts", "created_at"),)

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)  # LIMIT_BREACH/CIRCUIT_BREAKER...
    severity: Mapped[str] = mapped_column(String(16), default="warning")  # info/warning/critical
    symbol: Mapped[str | None] = mapped_column(String(32), nullable=True)
    detail: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[dict] = mapped_column(JSONB, default=dict)
    triggered_emergency_stop: Mapped[bool] = mapped_column(Boolean, default=False)


class SystemEvent(Base):
    __tablename__ = "system_events"
    __table_args__ = (Index("ix_sys_ts", "created_at"),)

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), default="info")
    message: Mapped[str] = mapped_column(Text, default="")
    context: Mapped[dict] = mapped_column(JSONB, default=dict)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    __table_args__ = (Index("ix_mv_name", "name"),)

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    model_type: Mapped[str] = mapped_column(String(64), default="")
    artifact_uri: Mapped[str] = mapped_column(Text, default="")
    metrics: Mapped[dict] = mapped_column(JSONB, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)


# Registry of all model classes for convenience (e.g. metadata create_all).
ALL_MODELS = [
    User, Asset, MarketData, News, EconomicEvent, Feature, Strategy, StrategyVersion,
    StrategyTest, Backtest, WalkForwardTest, MonteCarloTest, Signal, Order, Fill,
    Position, Trade, PortfolioSnapshot, MarketRegimeRow, ResearchHypothesis,
    KnowledgeMemory, LearningEvent, RiskEvent, SystemEvent, ModelVersion,
]
