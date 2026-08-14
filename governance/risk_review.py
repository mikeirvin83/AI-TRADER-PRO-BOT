"""Risk review checklist (Phase 12).

The RISK_REVIEW promotion stage is a structured, itemised sign-off. Every item
is either an automated assertion (evaluated from evidence the pipeline already
collected) or a manual attestation a human must tick. A single unmet mandatory
item blocks promotion — the checklist fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

from config.logging_config import get_logger

log = get_logger(__name__)


@dataclass
class ChecklistItem:
    """One reviewable item."""
    key: str
    description: str
    mandatory: bool = True
    automated: bool = False
    #: For automated items: callable(evidence) -> bool
    predicate: Optional[Callable[[Dict[str, Any]], bool]] = None
    satisfied: Optional[bool] = None
    attested_by: str = ""
    note: str = ""
    evaluated_at: Optional[datetime] = None

    def evaluate(self, evidence: Dict[str, Any]) -> Optional[bool]:
        if self.automated and self.predicate is not None:
            try:
                self.satisfied = bool(self.predicate(evidence))
            except Exception as exc:  # fail closed
                self.satisfied = False
                self.note = f"predicate_error: {exc}"
            self.evaluated_at = datetime.now(timezone.utc)
        return self.satisfied

    def attest(self, satisfied: bool, attested_by: str, note: str = "") -> None:
        if self.automated:
            raise ValueError(
                f"item '{self.key}' is automated and cannot be manually attested")
        if not attested_by:
            raise ValueError("attestation requires a named human attester")
        self.satisfied = bool(satisfied)
        self.attested_by = attested_by
        self.note = note
        self.evaluated_at = datetime.now(timezone.utc)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "description": self.description,
            "mandatory": self.mandatory,
            "automated": self.automated,
            "satisfied": self.satisfied,
            "attested_by": self.attested_by,
            "note": self.note,
            "evaluated_at": self.evaluated_at.isoformat() if self.evaluated_at else None,
        }


@dataclass
class RiskReviewResult:
    strategy: str
    passed: bool
    items: List[Dict[str, Any]] = field(default_factory=list)
    blocking: List[str] = field(default_factory=list)
    unanswered: List[str] = field(default_factory=list)
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "passed": self.passed,
            "blocking": list(self.blocking),
            "unanswered": list(self.unanswered),
            "items": list(self.items),
            "reviewed_at": self.reviewed_at.isoformat(),
        }


def _default_items() -> List[ChecklistItem]:
    """The standard mandatory risk review."""
    return [
        # ---- automated assertions, read from collected evidence ----
        ChecklistItem(
            "validation_stages_complete",
            "All automated validation gates (backtest, OOS, walk-forward, "
            "Monte Carlo, paper, shadow) passed in sequence.",
            automated=True,
            predicate=lambda e: bool(e.get("all_gates_passed")),
        ),
        ChecklistItem(
            "shadow_divergence_within_limit",
            "Shadow-vs-paper divergence is within the configured limit.",
            automated=True,
            predicate=lambda e: (
                e.get("shadow_divergence_pct") is not None
                and float(e["shadow_divergence_pct"]) <= float(
                    e.get("max_divergence_pct", 0.10))
            ),
        ),
        ChecklistItem(
            "position_limits_defined",
            "Per-symbol and portfolio position limits are configured.",
            automated=True,
            predicate=lambda e: bool(e.get("position_limits_defined")),
        ),
        ChecklistItem(
            "kill_switch_tested",
            "Kill switch and emergency stop verified in the current build.",
            automated=True,
            predicate=lambda e: bool(e.get("kill_switch_tested")),
        ),
        ChecklistItem(
            "drawdown_limits_configured",
            "Daily and total drawdown circuit breakers are configured.",
            automated=True,
            predicate=lambda e: bool(e.get("drawdown_limits_configured")),
        ),
        ChecklistItem(
            "no_open_degradation_alerts",
            "No unresolved strategy-degradation alerts.",
            automated=True,
            predicate=lambda e: not e.get("open_degradation_alerts"),
        ),
        ChecklistItem(
            "correlation_within_limits",
            "Correlation to existing live book is within limits.",
            automated=True,
            predicate=lambda e: (
                e.get("max_correlation") is None
                or float(e["max_correlation"]) <= float(e.get("correlation_limit", 0.7))
            ),
        ),
        # ---- manual attestations ----
        ChecklistItem(
            "capital_allocation_agreed",
            "Initial live capital allocation agreed and documented.",
        ),
        ChecklistItem(
            "failure_modes_understood",
            "Known failure modes and their mitigations reviewed.",
        ),
        ChecklistItem(
            "rollback_plan_documented",
            "Rollback / de-allocation plan documented and rehearsed.",
        ),
        ChecklistItem(
            "monitoring_and_alerting_ready",
            "Monitoring, alerting and on-call escalation confirmed working.",
        ),
        ChecklistItem(
            "broker_account_verified",
            "Broker account, credentials and permissions independently verified.",
        ),
    ]


class RiskReviewChecklist:
    """Structured RISK_REVIEW sign-off for a single strategy."""

    def __init__(
        self,
        strategy: str,
        items: Optional[List[ChecklistItem]] = None,
    ) -> None:
        self.strategy = strategy
        self.items: List[ChecklistItem] = items if items is not None else _default_items()
        self._by_key = {i.key: i for i in self.items}

    # -------------------------------------------------------------- #
    def item(self, key: str) -> ChecklistItem:
        if key not in self._by_key:
            raise KeyError(f"unknown checklist item: {key}")
        return self._by_key[key]

    @property
    def manual_items(self) -> List[ChecklistItem]:
        return [i for i in self.items if not i.automated]

    @property
    def automated_items(self) -> List[ChecklistItem]:
        return [i for i in self.items if i.automated]

    def attest(self, key: str, satisfied: bool, attested_by: str, note: str = "") -> ChecklistItem:
        item = self.item(key)
        item.attest(satisfied, attested_by, note)
        log.info("risk_review_attested", strategy=self.strategy, item=key,
                 satisfied=satisfied, by=attested_by)
        return item

    def evaluate_automated(self, evidence: Dict[str, Any]) -> None:
        for item in self.automated_items:
            item.evaluate(evidence)

    # -------------------------------------------------------------- #
    def review(self, evidence: Optional[Dict[str, Any]] = None) -> RiskReviewResult:
        """Evaluate the whole checklist. Fails closed on anything unanswered."""
        self.evaluate_automated(evidence or {})

        blocking: List[str] = []
        unanswered: List[str] = []
        for item in self.items:
            if item.satisfied is None:
                unanswered.append(item.key)
                if item.mandatory:
                    blocking.append(item.key)
            elif not item.satisfied and item.mandatory:
                blocking.append(item.key)

        passed = len(blocking) == 0
        result = RiskReviewResult(
            strategy=self.strategy,
            passed=passed,
            items=[i.to_dict() for i in self.items],
            blocking=blocking,
            unanswered=unanswered,
        )
        log.info("risk_review_complete", strategy=self.strategy, passed=passed,
                 blocking=len(blocking))
        return result

    def progress(self) -> Dict[str, Any]:
        answered = sum(1 for i in self.items if i.satisfied is not None)
        return {
            "strategy": self.strategy,
            "total": len(self.items),
            "answered": answered,
            "remaining": len(self.items) - answered,
        }
