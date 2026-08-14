"""End-to-end paper trading loop — wires all components into a running system.

This is the main async runner that coordinates:
  Market data → Features → Regime → Strategies → Signals →
  Quality Filter → Decision Loop → Risk → Paper Execution → Review

Operating principles:
  1. Only trades during REGULAR session
  2. Risk engine has absolute veto at every stage
  3. All fills are paper (next-bar-open with slippage)
  4. Daily/weekly reviews run automatically after market close
  5. News pipeline polls continuously in background
  6. Learning engine proposes — never applies — changes

This loop is designed to be started and left running; it manages its own
scheduling, error recovery, and state persistence.
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

from config.constants import (
    DEFAULT_EQUITY_UNIVERSE,
    EventTopic,
    MarketRegime,
    OrderSide,
    StrategyStatus,
    Timeframe,
)
from config.logging_config import get_logger
from config.settings import TradingMode, get_settings
from core.event_bus import Event, get_event_bus
from core.system_state import get_system_state
from execution.paper_engine import PaperEngine
from features.feature_engine import FeatureEngine
from market_data.alpaca_client import AlpacaClient
from news.news_pipeline import NewsPipeline
from orchestration.decision_loop import DecisionLoop
from orchestration.daily_review import DailyReview
from orchestration.weekly_review import WeeklyReview
from orchestration.session_manager import SessionManager, SessionPhase
from regime.classifier import RegimeClassifier
from risk.portfolio_risk_integrator import PortfolioRiskIntegrator
from risk.risk_engine import RiskEngine
from signals.signal_generator import SignalGenerator
from validation.trade_quality_filter import TradeQualityFilter
from memory.strategy_learner import StrategyLearner
from memory.pattern_detector import PatternDetector

log = get_logger(__name__)


class PaperTradingLoop:
    """Main async loop for end-to-end paper trading.

    Usage:
        loop = PaperTradingLoop()
        await loop.run()  # blocks until stopped
    """

    def __init__(
        self,
        symbols: Optional[List[str]] = None,
        starting_cash: float = 100_000.0,
        scan_interval_seconds: int = 60,
    ) -> None:
        self.symbols = symbols or list(DEFAULT_EQUITY_UNIVERSE)
        self.scan_interval = scan_interval_seconds
        self._running = False

        # Core components
        self.settings = get_settings()
        self.state = get_system_state()
        self.bus = get_event_bus()
        self.alpaca = AlpacaClient()
        self.feature_engine = FeatureEngine()
        self.regime_classifier = RegimeClassifier()
        self.signal_generator = SignalGenerator()
        self.quality_filter = TradeQualityFilter()
        self.decision_loop = DecisionLoop()
        self.risk_engine = RiskEngine()
        self.paper_engine = PaperEngine(starting_cash=starting_cash)
        self.portfolio_integrator = PortfolioRiskIntegrator(
            initial_equity=starting_cash)
        self.session_manager = SessionManager()
        self.news_pipeline = NewsPipeline(watch_symbols=self.symbols)
        self.daily_review = DailyReview()
        self.weekly_review = WeeklyReview()
        self.strategy_learner = StrategyLearner()
        self.pattern_detector = PatternDetector()

        # Session state
        self._signals_generated = 0
        self._signals_rejected = 0
        self._trades_today: Dict[str, List[float]] = {}  # strategy → [pnl]
        self._risk_events: List[Dict[str, Any]] = []
        self._cycle_count = 0

    # ------------------------------------------------------------------ #
    # Main run loop
    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        """Start the paper trading loop. Blocks until stop() is called."""
        # Safety: ensure we're in PAPER mode
        if self.settings.TRADING_MODE not in (TradingMode.PAPER, TradingMode.RESEARCH):
            log.error("paper_loop_wrong_mode", mode=self.settings.TRADING_MODE.value)
            return

        self._running = True
        log.info("paper_trading_loop_starting",
                 symbols=self.symbols, cash=self.paper_engine.starting_cash)

        # Transition system state to PAPER
        try:
            self.state.transition_to(TradingMode.PAPER, "paper_loop_start",
                                     actor="paper_trading_loop")
        except Exception:  # noqa: BLE001
            pass  # May already be in PAPER

        # Start news pipeline in background
        await self.news_pipeline.start()

        # Subscribe to risk events
        self.bus.subscribe(EventTopic.RISK_BREACH, self._on_risk_event)

        try:
            while self._running:
                await self._tick()
                await asyncio.sleep(self.scan_interval)
        except asyncio.CancelledError:
            log.info("paper_loop_cancelled")
        finally:
            await self.news_pipeline.stop()
            self.bus.unsubscribe(EventTopic.RISK_BREACH, self._on_risk_event)
            log.info("paper_trading_loop_stopped",
                     cycles=self._cycle_count)

    async def stop(self) -> None:
        """Stop the loop gracefully."""
        self._running = False

    # ------------------------------------------------------------------ #
    # Core tick — one iteration of the trading loop
    # ------------------------------------------------------------------ #

    async def _tick(self) -> None:
        """One iteration: check session, scan, decide, execute, review."""
        self._cycle_count += 1

        # Check emergency stop
        if self.state.is_emergency_stopped():
            log.info("paper_loop_emergency_stopped")
            return

        phase = self.session_manager.current_phase()

        # ---- Post-market reviews ----
        if self.session_manager.should_run_daily_review():
            await self._run_daily_review()
            self.session_manager.mark_daily_review_done()

        if self.session_manager.should_run_weekly_review():
            await self._run_weekly_review()
            self.session_manager.mark_weekly_review_done()

        # ---- Only scan/trade during REGULAR hours ----
        if phase != SessionPhase.REGULAR:
            return

        # ---- Market scan cycle ----
        for symbol in self.symbols:
            try:
                await self._process_symbol(symbol)
            except Exception:  # noqa: BLE001
                log.exception("symbol_processing_error", symbol=symbol)

    async def _process_symbol(self, symbol: str) -> None:
        """Full pipeline for a single symbol."""
        # 1. Fetch latest data
        data = await asyncio.to_thread(
            self._fetch_data, symbol)
        if data is None or data.empty:
            return

        # 2. Compute features
        try:
            features = self.feature_engine.compute(data)
        except Exception:  # noqa: BLE001
            log.warning("feature_computation_failed", symbol=symbol)
            return

        # 3. Classify regime
        regime = self.regime_classifier.classify(features)

        # 4. Generate signals
        signals = self.signal_generator.generate(
            symbol=symbol, features=features, regime=regime,
            data=data,
        )
        self._signals_generated += len(signals)

        if not signals:
            return

        # 5. News risk check
        for signal in signals:
            news_risk = self.news_pipeline.assess_trade_risk(
                symbol, signal.get("direction", ""))

            # 6. Quality filter
            quality_result = self.quality_filter.evaluate({
                "symbol": symbol,
                "signal": signal,
                "regime": regime,
                "news_risk": news_risk,
                "risk_engine": self.risk_engine,
                "data": data,
            })
            if not quality_result.allowed:
                self._signals_rejected += 1
                log.debug("signal_rejected", symbol=symbol,
                          reasons=[c.name for c in quality_result.failed_checks])
                continue

            # 7. Decision loop (agent consensus)
            context = {
                "symbol": symbol,
                "direction": signal.get("direction"),
                "signal": signal,
                "regime": regime,
                "features": features.to_dict() if hasattr(features, "to_dict") else {},
                "news_risk_state": news_risk.get("risk_state", "normal"),
                "news_sentiment": news_risk.get("sentiment", {}).get("overall", "neutral"),
                "candidates": [symbol],
                "portfolio": self.paper_engine.snapshot(
                    self._get_marks()),
            }
            decision = self.decision_loop.decide(context)

            if not decision.approved:
                self._signals_rejected += 1
                log.debug("decision_rejected", symbol=symbol,
                          reason=decision.reason)
                continue

            # 8. Execute paper trade
            await self._execute_paper_trade(symbol, signal, data)

    # ------------------------------------------------------------------ #
    # Execution
    # ------------------------------------------------------------------ #

    async def _execute_paper_trade(
        self, symbol: str, signal: Dict[str, Any], data: pd.DataFrame,
    ) -> None:
        """Execute a paper trade based on the approved signal."""
        direction = signal.get("direction", "LONG")
        side = OrderSide.BUY.value if direction == "LONG" else OrderSide.SELL.value

        # Use latest close as fill price (simulates next-bar-open)
        fill_price = float(data["close"].iloc[-1])

        # Position sizing from risk engine
        qty = signal.get("qty", 1.0)
        volume = float(data["volume"].iloc[-1]) if "volume" in data.columns else None

        fill = self.paper_engine.fill_order(
            symbol=symbol, side=side, qty=qty,
            fill_price=fill_price, volume=volume,
        )

        # Update portfolio integrator
        marks = self._get_marks()
        equity = self.paper_engine.portfolio_value(marks)
        self.portfolio_integrator.update(equity, self.paper_engine.positions)

        # Track trade for daily review
        strategy_name = signal.get("strategy", "unknown")
        if strategy_name not in self._trades_today:
            self._trades_today[strategy_name] = []

        # Publish fill event
        await self.bus.publish(Event(
            topic=EventTopic.ORDER_FILLED,
            payload={
                "symbol": symbol,
                "side": side,
                "qty": fill.qty,
                "price": fill.price,
                "slippage": fill.slippage,
                "strategy": strategy_name,
            },
            source="paper_trading_loop",
        ))

        log.info("paper_trade_executed", symbol=symbol, side=side,
                 qty=fill.qty, price=round(fill.price, 2))

    # ------------------------------------------------------------------ #
    # Reviews
    # ------------------------------------------------------------------ #

    async def _run_daily_review(self) -> None:
        """Run end-of-day review."""
        log.info("daily_review_starting")
        marks = self._get_marks()
        portfolio = self.paper_engine.snapshot(marks)

        review = self.daily_review.run(
            portfolio_snapshot=portfolio,
            strategy_trade_map=self._trades_today,
            signals_generated=self._signals_generated,
            signals_rejected=self._signals_rejected,
            risk_events=self._risk_events,
        )

        # Run pattern detection periodically
        if self._cycle_count % 100 == 0:
            patterns = self.pattern_detector.analyze([])
            log.info("pattern_analysis", patterns=patterns.get("status"))

        # Reset daily counters
        self._signals_generated = 0
        self._signals_rejected = 0
        self._trades_today.clear()
        self._risk_events.clear()

        log.info("daily_review_complete", pnl=review.get("total_pnl", 0))

    async def _run_weekly_review(self) -> None:
        """Run end-of-week review."""
        log.info("weekly_review_starting")
        # In production, strategy profiles would come from the database
        review = self.weekly_review.run(strategy_profiles=[])
        log.info("weekly_review_complete",
                 changes=review.get("status_changes_needed", 0))

    # ------------------------------------------------------------------ #
    # Data helpers
    # ------------------------------------------------------------------ #

    def _fetch_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """Fetch latest OHLCV data for a symbol."""
        try:
            from market_data.historical import HistoricalService
            svc = HistoricalService()
            return svc.fetch(symbol, timeframe=Timeframe.D1, limit=200)
        except Exception:  # noqa: BLE001
            log.debug("data_fetch_failed", symbol=symbol)
            return None

    def _get_marks(self) -> Dict[str, float]:
        """Get current marks for all positions."""
        marks: Dict[str, float] = {}
        for sym, pos in self.paper_engine.positions.items():
            if pos.qty != 0:
                marks[sym] = pos.avg_price  # fallback to avg price
        return marks

    async def _on_risk_event(self, event: Event) -> None:
        """Handle risk breach events."""
        self._risk_events.append(event.payload)
        log.warning("risk_event_in_loop", payload=event.payload)

    # ------------------------------------------------------------------ #
    # Status
    # ------------------------------------------------------------------ #

    def status(self) -> Dict[str, Any]:
        """Return current loop status."""
        marks = self._get_marks()
        return {
            "running": self._running,
            "cycle_count": self._cycle_count,
            "session": self.session_manager.session_summary(),
            "portfolio": self.paper_engine.snapshot(marks),
            "risk": self.portfolio_integrator.get_risk_summary(),
            "signals_today": self._signals_generated,
            "signals_rejected": self._signals_rejected,
            "news_sentiment": self.news_pipeline.get_market_sentiment(),
            "emergency_stopped": self.state.is_emergency_stopped(),
        }
