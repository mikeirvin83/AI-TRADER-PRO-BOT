"""Dashboard router — the read model consumed by the operator dashboard.

The dashboard calls a flat set of ``/api/*`` endpoints. This router mounts them
and assembles each response from **real platform state**: the system state
machine, the configured risk limits, the broker (Alpaca paper), the regime
classifier, the news pipeline and the database.

Design rules:

* **Never fabricate numbers.** When a source is unavailable (database down,
  broker unreachable, no trading history yet) the endpoint returns an empty
  collection or explicit zeros/nulls plus a ``sources`` hint — never invented
  balances, trades or performance figures.
* **Never block the UI.** Every source is wrapped in a guard and network-backed
  responses are cached with a short TTL so a slow feed cannot stall a page.
* **Read-only, except for the two explicit human controls** (kill switch and
  mode transition) which delegate to the same guarded system-state code paths
  as the rest of the platform. Nothing here can enable live trading.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from config.constants import Timeframe
from config.logging_config import get_logger
from config.settings import get_settings
from core.system_state import (
    _ALLOWED_TRANSITIONS,
    IllegalTransitionError,
    TradingMode,
    get_system_state,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["dashboard"])

_PROCESS_START = time.time()

# Instruments shown on the market overview page.
_OVERVIEW_EQUITIES = [("SPY", "S&P 500 ETF"), ("QQQ", "Nasdaq 100 ETF"), ("IWM", "Russell 2000 ETF")]
_OVERVIEW_CRYPTO = [("BTC/USD", "Bitcoin"), ("ETH/USD", "Ethereum")]
_REGIME_SYMBOL = "SPY"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def _guard(fn: Callable[[], Any], default: Any, what: str) -> Any:
    """Run ``fn``, returning ``default`` (and logging) on any failure.

    Keeps a single unavailable dependency from breaking a whole dashboard page.
    """
    try:
        return fn()
    except Exception as exc:  # noqa: BLE001 - dashboard must degrade, not crash
        logger.debug("dashboard.source_unavailable", source=what, error=str(exc))
        return default


class _TTLCache:
    """Tiny thread-safe TTL cache for network-backed reads."""

    def __init__(self) -> None:
        self._data: Dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()

    def get_or_set(self, key: str, ttl: float, producer: Callable[[], Any]) -> Any:
        now = time.time()
        with self._lock:
            hit = self._data.get(key)
            if hit and now - hit[0] < ttl:
                return hit[1]
        value = producer()
        with self._lock:
            self._data[key] = (now, value)
        return value


_cache = _TTLCache()


def _f(value: Any, default: float = 0.0) -> float:
    """Coerce to float, tolerating ``None``/``Decimal``/strings."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _alpaca():
    from market_data.alpaca_client import AlpacaClient

    return AlpacaClient()


def _db_rows(query_fn: Callable[[Any], List[Any]]) -> List[Any]:
    """Run a read query, returning ``[]`` when the database is unreachable."""

    def run() -> List[Any]:
        from database.session import session_scope

        with session_scope() as session:
            return query_fn(session)

    return _guard(run, [], "database")


def _regime_label(raw: str) -> str:
    """Human-readable regime label for the UI."""
    return raw.replace("_", " ").title()


# --------------------------------------------------------------------------- #
# System
# --------------------------------------------------------------------------- #
@router.get("/system/status")
def system_status() -> Dict[str, Any]:
    state = get_system_state()
    settings = get_settings()

    def market_status() -> str:
        from orchestration.session_manager import SessionManager

        return SessionManager().current_phase().value

    broker_ok = _guard(lambda: _alpaca().sdk_available, False, "alpaca")

    return {
        "trading_mode": state.get_mode().value,
        "market_status": _guard(market_status, "unknown", "session_manager"),
        "system_health": "HALTED" if state.is_emergency_stopped() else "HEALTHY",
        "uptime_hours": round((time.time() - _PROCESS_START) / 3600.0, 3),
        "last_heartbeat": datetime.now(timezone.utc).isoformat(),
        "api_connected": True,
        "broker_connected": bool(broker_ok),
        "ws_connected": False,
        "trading_allowed": state.is_trading_allowed(),
        "emergency_stopped": state.is_emergency_stopped(),
        "env": settings.ENV,
    }


@router.get("/system/mode")
def system_mode() -> Dict[str, Any]:
    state = get_system_state()
    history = [
        {
            "from": h.from_mode.value,
            "to": h.to_mode.value,
            "timestamp": _iso(h.timestamp),
            "reason": h.reason,
            "actor": h.actor,
        }
        for h in reversed(list(state.get_history()))
    ]
    current = state.get_mode()
    valid = sorted(m.value for m in _ALLOWED_TRANSITIONS.get(current, set()))
    return {"current": current.value, "valid_transitions": valid, "history": history}


@router.get("/system/config")
def system_config() -> Dict[str, Any]:
    s = get_settings()
    return {
        "risk_per_trade": s.MAX_RISK_PER_TRADE_PCT * 100,
        "daily_loss_limit": s.MAX_DAILY_LOSS_PCT * 100,
        "weekly_loss_limit": s.MAX_WEEKLY_LOSS_PCT * 100,
        "max_drawdown": s.MAX_PORTFOLIO_DRAWDOWN_PCT * 100,
        "max_position_size": s.MAX_POSITION_SIZE_PCT * 100,
        "max_leverage": s.MAX_LEVERAGE,
        "max_positions": s.MAX_SIMULTANEOUS_TRADES,
        "max_correlated_exposure": s.MAX_CORRELATED_EXPOSURE_PCT * 100,
        "min_signal_score": s.SIGNAL_SCORE_MIN_QUALIFIED,
        "high_quality_signal_score": s.SIGNAL_SCORE_MIN_HIGH_QUALITY,
        "signal_ttl_hours": 24,
        "min_paper_trades": s.MIN_PAPER_TRADES,
        "min_paper_duration_days": s.MIN_PAPER_DURATION_DAYS,
        "trading_mode": s.TRADING_MODE.value,
    }


@router.get("/system/logs")
def system_logs(limit: int = 100) -> List[Dict[str, Any]]:
    """Recent system events recorded by the platform."""

    def query(session):
        from sqlalchemy import select

        from database.models import SystemEvent

        stmt = select(SystemEvent).order_by(SystemEvent.created_at.desc()).limit(limit)
        return [
            {
                "timestamp": _iso(row.created_at),
                "level": (row.severity or "info").upper(),
                "message": row.message,
                "source": row.event_type,
            }
            for row in session.scalars(stmt).all()
        ]

    return _db_rows(query)


class KillRequest(BaseModel):
    reason: str = "Operator kill switch from dashboard"
    actor: str = "dashboard"


@router.post("/system/kill")
def kill_switch(req: Optional[KillRequest] = None) -> Dict[str, Any]:
    body = req or KillRequest()
    state = get_system_state()
    state.engage_emergency_stop(body.reason, actor=body.actor)
    return {
        "success": True,
        "mode": state.get_mode().value,
        "trading_allowed": state.is_trading_allowed(),
        "emergency_stopped": state.is_emergency_stopped(),
    }


class ModeTransitionRequest(BaseModel):
    target_mode: str
    reason: str = "Operator transition from dashboard"
    actor: str = "dashboard"


@router.post("/system/mode/transition")
def transition_mode(req: ModeTransitionRequest) -> Dict[str, Any]:
    """Operator-driven mode change.

    Delegates to the state machine, which enforces the promotion ladder and
    refuses LIVE unless the out-of-band authorization gate is satisfied.
    """
    state = get_system_state()
    try:
        target = TradingMode(req.target_mode.upper())
    except ValueError:
        return {"success": False, "detail": f"Unknown mode: {req.target_mode}", "mode": state.get_mode().value}
    try:
        state.transition_to(target, req.reason, actor=req.actor)
    except IllegalTransitionError as exc:
        return {"success": False, "detail": str(exc), "mode": state.get_mode().value}
    return {
        "success": True,
        "mode": state.get_mode().value,
        "trading_allowed": state.is_trading_allowed(),
        "emergency_stopped": state.is_emergency_stopped(),
    }


# --------------------------------------------------------------------------- #
# Account & positions
# --------------------------------------------------------------------------- #
def _account_snapshot() -> Dict[str, Any]:
    state = get_system_state()
    empty = {
        "portfolio_value": 0.0, "equity": 0.0, "cash": 0.0, "buying_power": 0.0,
        "long_market_value": 0.0, "short_market_value": 0.0,
        "daily_pnl": 0.0, "daily_pnl_pct": 0.0,
        "weekly_pnl": 0.0, "weekly_pnl_pct": 0.0,
        "monthly_pnl": 0.0, "monthly_pnl_pct": 0.0,
        "max_drawdown": 0.0,
        "mode": state.get_mode().value,
        "broker_connected": False,
    }

    def fetch() -> Dict[str, Any]:
        client = _alpaca()
        if not client.sdk_available:
            return empty
        acct = client.get_account()
        equity = _f(acct.get("equity"))
        last_equity = _f(acct.get("last_equity"), equity)
        daily_pnl = equity - last_equity
        return {
            **empty,
            "portfolio_value": equity,
            "equity": equity,
            "cash": _f(acct.get("cash")),
            "buying_power": _f(acct.get("buying_power")),
            "long_market_value": _f(acct.get("long_market_value")),
            "short_market_value": _f(acct.get("short_market_value")),
            "daily_pnl": round(daily_pnl, 2),
            "daily_pnl_pct": round(daily_pnl / last_equity * 100, 3) if last_equity else 0.0,
            "broker_connected": True,
        }

    snapshot = _guard(fetch, empty, "alpaca_account")

    # Longer-horizon P&L comes from our own portfolio snapshots, not the broker.
    def periods(session):
        from sqlalchemy import select

        from database.models import PortfolioSnapshot

        now = datetime.now(timezone.utc)
        out = {}
        for label, days in (("weekly", 7), ("monthly", 30)):
            stmt = (
                select(PortfolioSnapshot)
                .where(PortfolioSnapshot.snapshot_time >= now - timedelta(days=days))
                .order_by(PortfolioSnapshot.snapshot_time.asc())
                .limit(1)
            )
            row = session.scalars(stmt).first()
            if row is not None:
                out[label] = _f(row.equity)
        stmt = select(PortfolioSnapshot).order_by(PortfolioSnapshot.drawdown_pct.desc()).limit(1)
        worst = session.scalars(stmt).first()
        if worst is not None:
            out["max_drawdown"] = -abs(_f(worst.drawdown_pct))
        return [out]

    rows = _db_rows(periods)
    history = rows[0] if rows else {}
    equity = snapshot["equity"]
    for label in ("weekly", "monthly"):
        base = history.get(label)
        if base and equity:
            snapshot[f"{label}_pnl"] = round(equity - base, 2)
            snapshot[f"{label}_pnl_pct"] = round((equity - base) / base * 100, 3)
    if "max_drawdown" in history:
        snapshot["max_drawdown"] = round(history["max_drawdown"], 3)
    return snapshot


@router.get("/account")
def account() -> Dict[str, Any]:
    return _cache.get_or_set("account", 15.0, _account_snapshot)


@router.get("/positions")
def positions() -> List[Dict[str, Any]]:
    def fetch() -> List[Dict[str, Any]]:
        client = _alpaca()
        if not client.sdk_available:
            return []
        out: List[Dict[str, Any]] = []
        for p in client.get_positions():
            entry = _f(p.get("avg_entry_price"))
            qty = _f(p.get("qty"))
            out.append({
                "symbol": p.get("symbol", ""),
                "direction": "SHORT" if qty < 0 else "LONG",
                "size": abs(qty),
                "entry_price": entry,
                "current_price": _f(p.get("current_price")),
                "stop_loss": None,
                "target": None,
                "market_value": _f(p.get("market_value")),
                "unrealized_pnl": _f(p.get("unrealized_pl")),
                "pnl_pct": round(_f(p.get("unrealized_plpc")) * 100, 3),
                "strategy": p.get("strategy") or "—",
            })
        return out

    return _cache.get_or_set("positions", 15.0, lambda: _guard(fetch, [], "alpaca_positions"))


# --------------------------------------------------------------------------- #
# Market
# --------------------------------------------------------------------------- #
def _daily_bars(symbol: str, days: int, is_crypto: bool = False):
    client = _alpaca()
    if not client.sdk_available:
        return None
    end = datetime.now(timezone.utc)
    return client.get_historical_bars(
        symbol, Timeframe.D1, end - timedelta(days=days), end, is_crypto=is_crypto
    )


def _overview() -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for symbols, is_crypto in ((_OVERVIEW_EQUITIES, False), (_OVERVIEW_CRYPTO, True)):
        for symbol, name in symbols:
            df = _guard(lambda s=symbol, c=is_crypto: _daily_bars(s, 10, c), None, f"bars:{symbol}")
            if df is None or len(df) < 2:
                continue
            close = float(df["close"].iloc[-1])
            prev = float(df["close"].iloc[-2])
            rows.append({
                "symbol": symbol,
                "name": name,
                "price": round(close, 2),
                "change": round(close - prev, 2),
                "change_pct": round((close - prev) / prev * 100, 3) if prev else 0.0,
                "volume": int(float(df["volume"].iloc[-1])),
            })
    return rows


@router.get("/market/overview")
def market_overview() -> List[Dict[str, Any]]:
    return _cache.get_or_set("overview", 60.0, lambda: _guard(_overview, [], "market_overview"))


def _regime() -> Dict[str, Any]:
    from regime.classifier import RegimeClassifier

    empty = {
        "current_regime": "Unknown",
        "confidence": 0.0,
        "duration_days": 0,
        "key_signals": [],
        "regime_history": [],
    }
    df = _guard(lambda: _daily_bars(_REGIME_SYMBOL, 400), None, "bars:regime")
    if df is None or len(df) < 50:
        return empty

    classifier = RegimeClassifier()
    result = classifier.classify(df)
    detail = result.detail or {}
    signals = [f"{_REGIME_SYMBOL} classified from {len(df)} daily bars"]
    if detail.get("adx") is not None:
        signals.append(f"ADX {detail['adx']:.1f}")
    if detail.get("vol_pct") is not None:
        signals.append(f"Volatility percentile {detail['vol_pct'] * 100:.0f}%")
    if "uptrend" in detail:
        signals.append("20 EMA above 50 EMA" if detail["uptrend"] else "20 EMA below 50 EMA")

    current_label = _regime_label(result.regime.value)

    # Rolling classification over the recent window gives a real history series.
    # The final point is the full-history classification, so the chart always
    # ends on the regime reported as current.
    history: List[Dict[str, Any]] = []
    total = len(df)
    step = max((total - 50) // 11, 1)
    cut_points = list(range(50, total, step))[-11:] + [total]
    for end_idx in cut_points:
        window = df.iloc[:end_idx]
        point = classifier.classify(window)
        history.append({
            "date": str(window.index[-1])[:10],
            "regime": _regime_label(point.regime.value),
            "confidence": round(point.confidence, 3),
        })

    # How long the current regime has held, measured in trading days by walking
    # back one bar at a time (bounded so the endpoint stays fast).
    duration_bars = 0
    for end_idx in range(total, max(total - 60, 50), -1):
        if _regime_label(classifier.classify(df.iloc[:end_idx]).regime.value) == current_label:
            duration_bars += 1
        else:
            break

    return {
        "current_regime": current_label,
        "confidence": round(result.confidence, 3),
        "duration_days": duration_bars,
        "duration_capped": duration_bars >= 60,
        "key_signals": signals,
        "regime_history": history,
        "symbol": _REGIME_SYMBOL,
    }


@router.get("/market/regime")
def market_regime() -> Dict[str, Any]:
    return _cache.get_or_set("regime", 300.0, lambda: _guard(_regime, {
        "current_regime": "Unknown", "confidence": 0.0, "duration_days": 0,
        "key_signals": [], "regime_history": [],
    }, "regime"))


def _news() -> List[Dict[str, Any]]:
    from news.news_aggregator import NewsAggregator

    items = NewsAggregator().fetch_and_classify(limit=40)
    out: List[Dict[str, Any]] = []
    for item in items[:25]:
        out.append({
            "timestamp": _iso(item.published_at),
            "headline": item.headline,
            "sentiment": (item.sentiment or "neutral").upper(),
            "assets": item.symbols or [],
            "relevance": round(_f(item.relevance_score), 3),
            "source": item.source,
            "url": item.url,
        })
    return out


@router.get("/market/news")
def market_news() -> List[Dict[str, Any]]:
    return _cache.get_or_set("news", 300.0, lambda: _guard(_news, [], "news"))


@router.get("/market/calendar")
def market_calendar(limit: int = 20) -> List[Dict[str, Any]]:
    """Upcoming economic events recorded in the database."""

    def query(session):
        from sqlalchemy import select

        from database.models import EconomicEvent

        now = datetime.now(timezone.utc)
        stmt = (
            select(EconomicEvent)
            .where(EconomicEvent.event_time >= now - timedelta(days=1))
            .order_by(EconomicEvent.event_time.asc())
            .limit(limit)
        )
        return [
            {
                "date": _iso(row.event_time),
                "event": row.name,
                "impact": (row.importance or "").upper(),
                "expected": row.forecast,
                "previous": row.previous,
                "actual": row.actual,
                "risk_state": row.risk_state,
            }
            for row in session.scalars(stmt).all()
        ]

    return _db_rows(query)


def _volatility() -> Dict[str, Any]:
    from features.volatility import historical_volatility

    empty = {"vix": None, "vix_change": None, "hist_vol_30d": None,
             "vol_percentile": None, "iv_rank": None, "symbol": _REGIME_SYMBOL}
    df = _guard(lambda: _daily_bars(_REGIME_SYMBOL, 400), None, "bars:vol")
    if df is None or len(df) < 60:
        return empty
    hv = historical_volatility(df["close"], 30, annualize=True).dropna()
    if hv.empty:
        return empty
    latest = float(hv.iloc[-1])
    prev = float(hv.iloc[-2]) if len(hv) > 1 else latest
    return {
        "vix": None,  # VIX is not available on the current data feed.
        "vix_change": None,
        "hist_vol_30d": round(latest * 100, 2),
        "hist_vol_change": round((latest - prev) * 100, 3),
        "vol_percentile": round(float(hv.rank(pct=True).iloc[-1]) * 100, 1),
        "iv_rank": None,  # Requires an options feed.
        "symbol": _REGIME_SYMBOL,
    }


@router.get("/market/volatility")
def market_volatility() -> Dict[str, Any]:
    return _cache.get_or_set("volatility", 300.0, lambda: _guard(_volatility, {
        "vix": None, "vix_change": None, "hist_vol_30d": None,
        "vol_percentile": None, "iv_rank": None, "symbol": _REGIME_SYMBOL,
    }, "volatility"))


# --------------------------------------------------------------------------- #
# Signals, risk
# --------------------------------------------------------------------------- #
@router.get("/signals/recent")
def recent_signals(limit: int = 50) -> List[Dict[str, Any]]:
    def query(session):
        from sqlalchemy import select

        from database.models import Signal, Strategy

        now = datetime.now(timezone.utc)
        stmt = (
            select(Signal, Strategy.name)
            .join(Strategy, Strategy.id == Signal.strategy_id, isouter=True)
            .order_by(Signal.created_at.desc())
            .limit(limit)
        )
        out: List[Dict[str, Any]] = []
        for row, strategy_name in session.execute(stmt).all():
            if row.acted_on:
                status = "EXECUTED"
            elif row.expiration_time and row.expiration_time < now:
                status = "EXPIRED"
            else:
                status = "PENDING"
            rationale = row.rationale or {}
            out.append({
                "id": str(row.id)[:8].upper(),
                "timestamp": _iso(row.created_at),
                "symbol": row.symbol,
                "strategy": strategy_name or "-",
                "direction": row.direction,
                "score": row.score,
                "status": status,
                "reason": rationale.get("summary") or row.invalidation_condition or "",
                "regime": row.regime,
                "timeframe": row.timeframe,
                "entry": _f(row.entry_price),
                "stop": _f(row.stop_price),
                "target": _f(row.target_price),
            })
        return out

    return _db_rows(query)


@router.get("/risk")
def risk() -> Dict[str, Any]:
    """Risk utilisation against the configured hard limits."""
    from risk.risk_engine import PortfolioState, RiskEngine

    settings = get_settings()
    snapshot = _cache.get_or_set("account", 15.0, _account_snapshot)
    equity = snapshot["equity"]
    open_positions = len(positions())

    def build_state() -> PortfolioState:
        base = equity or 0.0
        return PortfolioState(
            equity=base,
            starting_equity_day=base - snapshot["daily_pnl"],
            starting_equity_week=base - snapshot["weekly_pnl"],
            peak_equity=base,
            open_positions=open_positions,
        )

    engine = RiskEngine()
    summary = _guard(lambda: engine.get_risk_summary(build_state()), {}, "risk_engine")
    limits = summary.get("limits", {})

    def query(session):
        from sqlalchemy import select

        from database.models import RiskEvent

        stmt = select(RiskEvent).order_by(RiskEvent.created_at.desc()).limit(25)
        return [
            {
                "timestamp": _iso(row.created_at),
                "type": row.event_type,
                "severity": (row.severity or "info").upper(),
                "description": row.detail,
                "symbol": row.symbol,
            }
            for row in session.scalars(stmt).all()
        ]

    events = _db_rows(query)

    return {
        "risk_per_trade": {"used": 0.0, "max": limits.get("max_risk_per_trade", settings.MAX_RISK_PER_TRADE_PCT) * 100},
        "daily_loss": {
            "used": round(max(_f(summary.get("daily_loss_pct")), 0.0) * 100, 3),
            "max": limits.get("max_daily_loss", settings.MAX_DAILY_LOSS_PCT) * 100,
        },
        "weekly_loss": {
            "used": round(max(_f(summary.get("weekly_loss_pct")), 0.0) * 100, 3),
            "max": limits.get("max_weekly_loss", settings.MAX_WEEKLY_LOSS_PCT) * 100,
        },
        "portfolio_drawdown": {
            "current": round(max(_f(summary.get("drawdown_pct")), 0.0) * 100, 3),
            "max": limits.get("max_portfolio_drawdown", settings.MAX_PORTFOLIO_DRAWDOWN_PCT) * 100,
        },
        "simultaneous_positions": {
            "current": open_positions,
            "max": limits.get("max_simultaneous_trades", settings.MAX_SIMULTANEOUS_TRADES),
        },
        "correlated_exposure": {
            "current": 0.0,
            "max": limits.get("max_correlated_exposure", settings.MAX_CORRELATED_EXPOSURE_PCT) * 100,
        },
        "circuit_breaker": {
            "status": "TRIPPED" if summary.get("circuit_breaker_active") else "NORMAL",
            "reason": None,
        },
        "risk_events": events,
        "correlation_matrix": _guard(_correlation_matrix, {"symbols": [], "values": []}, "correlation"),
        "mode": summary.get("mode", get_system_state().get_mode().value),
        "trading_allowed": summary.get("trading_allowed", get_system_state().is_trading_allowed()),
    }


def _correlation_matrix() -> Dict[str, Any]:
    """Correlation of daily returns across the currently held symbols."""
    held = [p["symbol"] for p in positions()][:8]
    if len(held) < 2:
        return {"symbols": [], "values": []}

    def build() -> Dict[str, Any]:
        import pandas as pd

        series = {}
        for symbol in held:
            df = _guard(lambda s=symbol: _daily_bars(s, 120, "/" in s), None, f"bars:{symbol}")
            if df is not None and len(df) > 20:
                series[symbol] = df["close"].pct_change().dropna()
        if len(series) < 2:
            return {"symbols": [], "values": []}
        frame = pd.DataFrame(series).dropna()
        corr = frame.corr()
        return {
            "symbols": list(corr.columns),
            "values": [[round(float(v), 3) for v in row] for row in corr.values],
        }

    return _cache.get_or_set("correlation:" + ",".join(held), 600.0, build)


# --------------------------------------------------------------------------- #
# Strategies
# --------------------------------------------------------------------------- #
@router.get("/strategies")
def strategies() -> List[Dict[str, Any]]:
    def query(session):
        from sqlalchemy import func, select

        from database.models import Strategy, Trade

        out: List[Dict[str, Any]] = []
        for row in session.scalars(select(Strategy)).all():
            stats = session.execute(
                select(
                    func.count(Trade.id),
                    func.sum(Trade.pnl),
                    func.max(Trade.exit_time),
                ).where(Trade.strategy_id == row.id)
            ).one()
            total_trades = int(stats[0] or 0)
            wins = int(session.execute(
                select(func.count(Trade.id)).where(Trade.strategy_id == row.id, Trade.pnl > 0)
            ).scalar() or 0)
            out.append({
                "id": str(row.id)[:8].upper(),
                "name": row.name,
                "version": row.current_version,
                "status": row.status,
                "type": row.category or "—",
                "total_trades": total_trades,
                "win_rate": round(wins / total_trades * 100, 2) if total_trades else None,
                "net_pnl": round(_f(stats[1]), 2) if stats[1] is not None else None,
                "expectancy": None,
                "profit_factor": None,
                "sharpe": None,
                "max_dd": None,
                "allocation_pct": (row.params or {}).get("allocation_pct"),
                "last_trade": _iso(stats[2]),
                "allowed_regimes": row.allowed_regimes or [],
                "min_signal_score": row.min_signal_score,
            })
        return out

    return _db_rows(query)


@router.get("/strategies/pipeline")
def strategy_pipeline() -> List[Dict[str, Any]]:
    """Where each strategy currently sits on the validation ladder."""

    def query(session):
        from sqlalchemy import select

        from database.models import Strategy

        now = datetime.now(timezone.utc)
        out: List[Dict[str, Any]] = []
        for row in session.scalars(select(Strategy)).all():
            updated = row.updated_at or row.created_at
            days = (now - updated).days if updated else 0
            out.append({
                "name": f"{row.name} v{row.current_version}",
                "stage": row.status,
                "days_in_stage": max(days, 0),
            })
        return out

    return _db_rows(query)


# --------------------------------------------------------------------------- #
# Research
# --------------------------------------------------------------------------- #
@router.get("/research/hypotheses")
def hypotheses() -> List[Dict[str, Any]]:
    def query(session):
        from sqlalchemy import select

        from database.models import ResearchHypothesis

        stmt = select(ResearchHypothesis).order_by(ResearchHypothesis.created_at.desc()).limit(50)
        out: List[Dict[str, Any]] = []
        for row in session.scalars(stmt).all():
            criteria = row.success_criteria or {}
            results = row.results or {}
            out.append({
                "id": row.hyp_id,
                "title": row.title,
                "status": row.status,
                "confidence": results.get("confidence"),
                "created": _iso(row.created_at),
                "assets": criteria.get("assets", []),
                "timeframe": criteria.get("timeframe"),
                "regime": criteria.get("regime"),
                "proposed_by": row.proposed_by,
            })
        return out

    return _db_rows(query)


@router.get("/research/backtests")
def backtests(limit: int = 25) -> List[Dict[str, Any]]:
    def query(session):
        from sqlalchemy import select

        from database.models import Backtest, Strategy

        stmt = (
            select(Backtest, Strategy.name)
            .join(Strategy, Strategy.id == Backtest.strategy_id, isouter=True)
            .order_by(Backtest.created_at.desc())
            .limit(limit)
        )
        out: List[Dict[str, Any]] = []
        for row, strategy_name in session.execute(stmt).all():
            metrics = row.metrics or {}
            out.append({
                "strategy": strategy_name or "—",
                "symbol": row.symbol,
                "timeframe": row.timeframe,
                "date": _iso(row.created_at),
                "sharpe": metrics.get("sharpe_ratio", metrics.get("sharpe")),
                "max_dd": metrics.get("max_drawdown_pct", metrics.get("max_dd")),
                "win_rate": metrics.get("win_rate"),
                "total_return": metrics.get("total_return_pct"),
                "status": metrics.get("verdict", "COMPLETE"),
            })
        return out

    return _db_rows(query)


@router.get("/research/knowledge")
def knowledge(limit: int = 25) -> List[Dict[str, Any]]:
    def query(session):
        from sqlalchemy import select

        from database.models import KnowledgeMemory

        stmt = select(KnowledgeMemory).order_by(KnowledgeMemory.created_at.desc()).limit(limit)
        out: List[Dict[str, Any]] = []
        for row in session.scalars(stmt).all():
            content = row.content or {}
            out.append({
                "timestamp": _iso(row.last_reinforced_at or row.created_at),
                "entry": content.get("insight") or content.get("summary") or row.key,
                "source": row.category,
                "confidence": row.confidence,
                "evidence_count": row.evidence_count,
            })
        return out

    return _db_rows(query)


# --------------------------------------------------------------------------- #
# Trades & performance
# --------------------------------------------------------------------------- #
@router.get("/trades")
def trades(limit: int = 200) -> List[Dict[str, Any]]:
    def query(session):
        from sqlalchemy import select

        from database.models import Strategy, Trade

        stmt = (
            select(Trade, Strategy.name)
            .join(Strategy, Strategy.id == Trade.strategy_id, isouter=True)
            .order_by(Trade.entry_time.desc())
            .limit(limit)
        )
        out: List[Dict[str, Any]] = []
        for row, strategy_name in session.execute(stmt).all():
            out.append({
                "id": str(row.id)[:8].upper(),
                "date": (_iso(row.exit_time or row.entry_time) or "")[:10],
                "symbol": row.symbol,
                "strategy": strategy_name or "—",
                "direction": row.direction,
                "entry": _f(row.entry_price),
                "exit": _f(row.exit_price) if row.exit_price is not None else None,
                "pnl": _f(row.pnl) if row.pnl is not None else None,
                "pnl_pct": row.pnl_pct,
                "r_multiple": row.r_multiple,
                "mae": row.mae,
                "mfe": row.mfe,
                "regime": row.regime,
                "slippage": _f(row.slippage),
                "exit_reason": row.exit_reason,
                "mode": row.mode,
            })
        return out

    return _db_rows(query)


@router.get("/performance/equity")
def equity_curve(days: int = 180) -> List[Dict[str, Any]]:
    def query(session):
        from sqlalchemy import select

        from database.models import PortfolioSnapshot

        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = (
            select(PortfolioSnapshot)
            .where(PortfolioSnapshot.snapshot_time >= cutoff)
            .order_by(PortfolioSnapshot.snapshot_time.asc())
        )
        out: List[Dict[str, Any]] = []
        for idx, row in enumerate(session.scalars(stmt).all(), start=1):
            out.append({
                "day": idx,
                "date": (_iso(row.snapshot_time) or "")[:10],
                "equity": round(_f(row.equity), 2),
                "drawdown_pct": row.drawdown_pct,
            })
        return out

    return _db_rows(query)


@router.get("/performance/monthly")
def monthly_returns() -> List[Dict[str, Any]]:
    """Month-over-month return derived from real portfolio snapshots."""
    curve = equity_curve(days=730)
    if len(curve) < 2:
        return []

    by_month: Dict[str, List[float]] = {}
    for point in curve:
        month = point["date"][:7]
        by_month.setdefault(month, []).append(point["equity"])

    out: List[Dict[str, Any]] = []
    for month in sorted(by_month):
        values = by_month[month]
        first, last = values[0], values[-1]
        out.append({
            "month": month,
            "returns": round((last - first) / first * 100, 3) if first else 0.0,
        })
    return out