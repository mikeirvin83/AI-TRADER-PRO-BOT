"""Event-driven backtest engine.

Processes bars strictly sequentially. A strategy only ever sees data up to and
including the current bar; orders generated on bar *t* fill at the OPEN of bar
*t+1*. This guarantees there is no look-ahead bias.

Cost model:
* commission : per-share (default 0 for Alpaca stocks/crypto)
* spread     : half-spread applied to the fill
* slippage   : none | fixed_bps | volume_based
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config.constants import MarketRegime, SignalDirection
from config.logging_config import get_logger
from backtesting.metrics import PerformanceMetrics, compute_metrics
from features.feature_engine import FeatureEngine
from regime.classifier import RegimeClassifier
from strategies.base_strategy import BaseStrategy

log = get_logger(__name__)


@dataclass
class BacktestConfig:
    initial_capital: float = 100_000.0
    commission_per_share: float = 0.0
    half_spread_bps: float = 0.0
    slippage_model: str = "fixed_bps"   # none | fixed_bps | volume_based
    slippage_bps: float = 1.0
    risk_fraction: float = 0.01
    warmup_bars: int = 50


@dataclass
class BacktestResult:
    metrics: PerformanceMetrics
    equity_curve: List[float] = field(default_factory=list)
    trades: List[Dict[str, Any]] = field(default_factory=list)
    config: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "metrics": self.metrics.to_dict(),
            "equity_curve": self.equity_curve,
            "trades": self.trades,
            "config": self.config,
        }


class BacktestEngine:
    def __init__(self, config: Optional[BacktestConfig] = None,
                 feature_engine: Optional[FeatureEngine] = None,
                 regime_classifier: Optional[RegimeClassifier] = None) -> None:
        self.cfg = config or BacktestConfig()
        self.features = feature_engine or FeatureEngine()
        self.regime = regime_classifier or RegimeClassifier()

    # ------------------------------------------------------------------ #
    def _slip(self, price: float, side: str, volume: float) -> float:
        model = self.cfg.slippage_model
        if model == "none":
            adj = 0.0
        elif model == "volume_based":
            base = self.cfg.slippage_bps / 10_000.0
            factor = 1.0 if volume <= 0 else min(3.0, 1e6 / max(volume, 1.0))
            adj = price * base * factor
        else:  # fixed_bps
            adj = price * self.cfg.slippage_bps / 10_000.0
        half_spread = price * self.cfg.half_spread_bps / 10_000.0
        total = adj + half_spread
        return price + total if side == "buy" else price - total

    def run(self, strategy: BaseStrategy, data: pd.DataFrame, symbol: str = "TEST",
            timeframe: str = "1Day") -> BacktestResult:
        """Run a single-symbol backtest."""
        data = data.copy()
        data.attrs["symbol"] = symbol
        data.attrs["timeframe"] = timeframe
        required = {"open", "high", "low", "close", "volume"}
        if not required.issubset(data.columns):
            raise ValueError(f"data missing columns: {required - set(data.columns)}")

        cash = self.cfg.initial_capital
        position_qty = 0.0
        position_entry = 0.0
        position_dir: Optional[SignalDirection] = None
        stop_price = target_price = 0.0

        equity_curve: List[float] = []
        period_returns: List[float] = []
        trade_pnls: List[float] = []
        trades: List[Dict[str, Any]] = []
        bars_in_market = 0

        # Precompute features once over the whole frame, then slice progressively.
        feat_all = self.features.build(data).features

        pending_signal: Optional[Any] = None
        prev_equity = self.cfg.initial_capital

        n = len(data)
        for i in range(self.cfg.warmup_bars, n):
            bar = data.iloc[i]
            price_open = float(bar["open"])
            price_close = float(bar["close"])
            volume = float(bar["volume"])

            # --- 1. Execute any pending order at THIS bar's open (no look-ahead) ---
            if pending_signal is not None and position_qty == 0:
                side = "buy" if pending_signal.direction == SignalDirection.LONG else "sell"
                fill = self._slip(price_open, side, volume)
                risk_per_unit = abs(pending_signal.entry - pending_signal.stop) or (price_open * 0.01)
                qty = np.floor((cash * self.cfg.risk_fraction) / risk_per_unit)
                if qty > 0:
                    commission = self.cfg.commission_per_share * qty
                    position_qty = qty if side == "buy" else -qty
                    position_entry = fill
                    position_dir = pending_signal.direction
                    stop_price = pending_signal.stop
                    target_price = pending_signal.target
                    cash -= position_qty * fill + commission
                    trades.append({"symbol": symbol, "side": side, "entry": fill, "qty": qty,
                                   "entry_index": i, "strategy": strategy.name, "status": "open"})
                pending_signal = None

            # --- 2. Manage open position: check stop / target intrabar ---
            if position_qty != 0 and position_dir is not None:
                bars_in_market += 1
                exit_price = None
                reason = None
                if position_dir == SignalDirection.LONG:
                    if float(bar["low"]) <= stop_price:
                        exit_price, reason = stop_price, "stop"
                    elif float(bar["high"]) >= target_price:
                        exit_price, reason = target_price, "target"
                else:
                    if float(bar["high"]) >= stop_price:
                        exit_price, reason = stop_price, "stop"
                    elif float(bar["low"]) <= target_price:
                        exit_price, reason = target_price, "target"

                if exit_price is not None:
                    side = "sell" if position_qty > 0 else "buy"
                    fill = self._slip(exit_price, side, volume)
                    commission = self.cfg.commission_per_share * abs(position_qty)
                    pnl = (fill - position_entry) * position_qty - commission
                    cash += position_qty * fill - commission
                    trade_pnls.append(pnl)
                    for t in reversed(trades):
                        if t["status"] == "open":
                            t.update({"exit": fill, "exit_index": i, "pnl": pnl,
                                      "exit_reason": reason, "status": "closed"})
                            break
                    position_qty = 0.0
                    position_dir = None

            # --- 3. Generate a new signal from data up to (and incl.) this bar ---
            if position_qty == 0 and pending_signal is None:
                window = data.iloc[: i + 1]
                fwin = feat_all.iloc[: i + 1]
                try:
                    regime_res = self.regime.classify(window)
                    sig = strategy.generate_signal(window, fwin, regime_res.regime, None)
                except Exception:  # noqa: BLE001
                    sig = None
                if sig is not None:
                    pending_signal = sig

            # --- 4. Mark-to-market equity ---
            mtm = cash + (position_qty * price_close if position_qty else 0.0)
            equity_curve.append(mtm)
            period_returns.append((mtm - prev_equity) / prev_equity if prev_equity else 0.0)
            prev_equity = mtm

        exposure = bars_in_market / max(1, (n - self.cfg.warmup_bars))
        metrics = compute_metrics(trade_pnls, equity_curve, period_returns,
                                  n_periods=len(equity_curve), exposure_time=exposure)
        log.info("backtest_complete", symbol=symbol, trades=metrics.num_trades,
                 total_return=round(metrics.total_return, 4))
        return BacktestResult(metrics, equity_curve, trades, self.cfg.__dict__)
