"""Trade Quality Filter (Section 35).

Only trade when ALL conditions are met. The default decision is NO TRADE.
A high-quality trading system is comfortable sitting in cash.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from config.constants import StrategyStatus
from config.logging_config import get_logger
from config.settings import Settings, get_settings
from core.system_state import get_system_state

log = get_logger(__name__)


@dataclass
class QualityCheck:
    name: str
    passed: bool
    value: Any = None
    threshold: Any = None
    detail: str = ""


@dataclass
class TradeQualityDecision:
    allowed: bool
    checks: List[QualityCheck] = field(default_factory=list)
    reason: str = ""

    @property
    def failed_checks(self) -> List[QualityCheck]:
        return [c for c in self.checks if not c.passed]


class TradeQualityFilter:
    """Aggregates ALL pre-trade conditions from Section 35.

    Every check is explicit and logged. If ANY fails, the trade is rejected.
    """

    def __init__(self, settings: Optional[Settings] = None) -> None:
        self.settings = settings or get_settings()
        self.state = get_system_state()

    def evaluate(self, context: Dict[str, Any]) -> TradeQualityDecision:
        checks: List[QualityCheck] = []

        # 1. Market data is valid
        data_quality = context.get("data_quality", "UNKNOWN")
        checks.append(QualityCheck(
            "market_data_valid", data_quality == "CLEAN",
            data_quality, "CLEAN",
            f"data_quality={data_quality}"))

        # 2. Liquidity is sufficient
        avg_volume = context.get("avg_volume", 0)
        min_volume = context.get("min_volume_threshold", 100_000)
        checks.append(QualityCheck(
            "liquidity_sufficient", avg_volume >= min_volume,
            avg_volume, min_volume))

        # 3. Spread is acceptable
        spread_pct = context.get("spread_pct", 1.0)
        max_spread = context.get("max_spread_pct", 0.005)  # 0.5% max spread
        checks.append(QualityCheck(
            "spread_acceptable", spread_pct <= max_spread,
            spread_pct, max_spread))

        # 4. Strategy is active
        strategy_status = context.get("strategy_status", "UNDER_RESEARCH")
        active_statuses = (StrategyStatus.ACTIVE.value, StrategyStatus.WATCH.value)
        checks.append(QualityCheck(
            "strategy_active", strategy_status in active_statuses,
            strategy_status, active_statuses))

        # 5. Strategy is validated (has passed backtesting)
        is_validated = context.get("strategy_validated", False)
        checks.append(QualityCheck(
            "strategy_validated", is_validated, is_validated, True))

        # 6. Market regime is appropriate
        regime_allowed = context.get("regime_allowed", False)
        checks.append(QualityCheck(
            "regime_appropriate", regime_allowed, regime_allowed, True))

        # 7. Signal passes minimum score
        score = context.get("signal_score", 0)
        min_score = self.settings.SIGNAL_SCORE_MIN_QUALIFIED
        checks.append(QualityCheck(
            "signal_score_sufficient", score >= min_score,
            score, min_score))

        # 8. Risk/reward passes minimum threshold
        rr = context.get("risk_reward", 0)
        min_rr = context.get("min_risk_reward", 1.5)
        checks.append(QualityCheck(
            "risk_reward_acceptable", rr >= min_rr,
            rr, min_rr))

        # 9. No emergency condition
        emergency = not self.state.is_trading_allowed()
        checks.append(QualityCheck(
            "no_emergency", not emergency,
            self.state.get_mode().value, "not EMERGENCY_STOP/DISABLED"))

        # 10. Risk engine approved (passed separately but recorded)
        risk_approved = context.get("risk_approved", False)
        checks.append(QualityCheck(
            "risk_approved", risk_approved, risk_approved, True))

        # Overall decision
        all_passed = all(c.passed for c in checks)
        failed = [c.name for c in checks if not c.passed]
        reason = "all_checks_passed" if all_passed else f"failed:{','.join(failed)}"

        if not all_passed:
            log.info("trade_quality_rejected", failed=failed,
                     symbol=context.get("symbol", "?"))

        return TradeQualityDecision(all_passed, checks, reason)
