"""Live trading authorization gate (Phase 12).

This is the single, narrow chokepoint between a fully validated strategy and
real capital. It is DENY-BY-DEFAULT and requires **all** of the following,
simultaneously:

  1. The strategy has reached the APPROVAL stage having passed every prior
     automated gate in sequence (backtest → OOS → walk-forward → Monte Carlo
     → paper → shadow → risk review).
  2. A completed RISK_REVIEW checklist with no blocking items.
  3. A currently-valid, unexpired, unrevoked approval record carrying sign-off
     from BOTH a risk officer and the portfolio owner (no self-approval, no
     single-person authorisation).
  4. An explicit operator-set environment authorisation
     (``LIVE_TRADING_AUTHORIZED=true``) — code alone can never satisfy this.
  5. The system not being emergency-stopped, and a capital cap being set.

If any condition is unmet the gate returns a denial with the exact reasons.
The gate NEVER changes the system mode by itself; it only issues an
authorization object that a human-initiated action may then present.

Current posture: live trading is NOT authorised. The default operating mode is
PAPER and this gate exists to keep it that way until every condition above is
deliberately and verifiably satisfied by humans.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger
from config.settings import TradingMode, get_settings
from core.system_state import get_system_state
from governance.approval_registry import (
    REQUIRED_ROLES,
    ApprovalRecord,
    ApprovalRegistry,
    ApprovalStatus,
    get_approval_registry,
)
from governance.risk_review import RiskReviewResult

log = get_logger(__name__)

#: Environment variable an operator must set OUT OF BAND to permit live trading.
LIVE_AUTH_ENV_VAR = "LIVE_TRADING_AUTHORIZED"

#: Action string used for live-promotion approval records.
ACTION_PROMOTE_TO_LIVE = "PROMOTE_TO_LIVE"

#: An issued authorization is valid for this long before it must be re-issued.
DEFAULT_AUTH_TTL_HOURS = 24


class LiveAuthorizationError(RuntimeError):
    """Raised when live trading is attempted without a valid authorization."""


@dataclass
class LiveTradingAuthorization:
    """A time-boxed, capital-capped permission to trade live capital."""
    strategy: str
    approval_request_id: str
    max_capital: float
    issued_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    ttl_hours: int = DEFAULT_AUTH_TTL_HOURS
    issued_by: str = "governance"
    conditions: List[str] = field(default_factory=list)
    revoked: bool = False
    revocation_reason: str = ""

    def is_valid(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        if self.revoked:
            return False
        return now <= self.issued_at + timedelta(hours=self.ttl_hours)

    def revoke(self, reason: str) -> None:
        self.revoked = True
        self.revocation_reason = reason
        log.warning("live_authorization_revoked", strategy=self.strategy, reason=reason)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "approval_request_id": self.approval_request_id,
            "max_capital": self.max_capital,
            "issued_at": self.issued_at.isoformat(),
            "ttl_hours": self.ttl_hours,
            "issued_by": self.issued_by,
            "conditions": list(self.conditions),
            "revoked": self.revoked,
            "revocation_reason": self.revocation_reason,
            "valid": self.is_valid(),
        }


@dataclass
class AuthorizationCheck:
    """Outcome of evaluating the live authorization gate."""
    strategy: str
    authorized: bool
    reasons: List[str] = field(default_factory=list)
    satisfied: List[str] = field(default_factory=list)
    authorization: Optional[LiveTradingAuthorization] = None
    checked_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "strategy": self.strategy,
            "authorized": self.authorized,
            "reasons": list(self.reasons),
            "satisfied": list(self.satisfied),
            "authorization": self.authorization.to_dict() if self.authorization else None,
            "checked_at": self.checked_at.isoformat(),
        }


class LiveAuthorizationGate:
    """Deny-by-default gate guarding the transition to live capital."""

    def __init__(
        self,
        registry: Optional[ApprovalRegistry] = None,
        max_capital_cap: float = 0.0,
    ) -> None:
        self.registry = registry or get_approval_registry()
        #: Hard ceiling on capital any single authorization may grant.
        self.max_capital_cap = max_capital_cap
        self.settings = get_settings()
        self.state = get_system_state()
        self._issued: Dict[str, LiveTradingAuthorization] = {}

    # -------------------------------------------------------------- #
    # Environment authorisation
    # -------------------------------------------------------------- #
    @staticmethod
    def env_authorized() -> bool:
        """True only if an operator explicitly set the env var to a true value."""
        raw = os.getenv(LIVE_AUTH_ENV_VAR, "")
        return raw.strip().lower() in {"1", "true", "yes", "on"}

    # -------------------------------------------------------------- #
    # Requesting approval
    # -------------------------------------------------------------- #
    def request_live_approval(
        self,
        strategy: str,
        requested_by: str = "system",
        context: Optional[Dict[str, Any]] = None,
    ) -> ApprovalRecord:
        """Open a human approval request for promoting a strategy to live."""
        return self.registry.request(
            subject=strategy,
            action=ACTION_PROMOTE_TO_LIVE,
            requested_by=requested_by,
            context=context or {},
        )

    # -------------------------------------------------------------- #
    # Evaluation
    # -------------------------------------------------------------- #
    def evaluate(
        self,
        strategy: str,
        validation_summary: Optional[Dict[str, Any]] = None,
        risk_review: Optional[RiskReviewResult] = None,
        requested_capital: float = 0.0,
        now: Optional[datetime] = None,
    ) -> AuthorizationCheck:
        """Evaluate every condition. Returns a denial listing what is missing."""
        now = now or datetime.now(timezone.utc)
        reasons: List[str] = []
        satisfied: List[str] = []

        # 1. Automated validation must be complete.
        vs = validation_summary or {}
        stage = str(vs.get("current_stage", "")).upper()
        if not vs:
            reasons.append("no_validation_summary")
        elif not vs.get("all_gates_passed"):
            reasons.append("automated_gates_not_all_passed")
        elif stage not in {"APPROVAL", "LIVE"}:
            reasons.append(f"stage_not_at_approval(current={stage or 'UNKNOWN'})")
        else:
            satisfied.append("automated_validation_complete")

        # 2. Risk review must have passed with nothing blocking.
        if risk_review is None:
            reasons.append("risk_review_missing")
        elif not risk_review.passed:
            reasons.append(
                "risk_review_blocking:" + ",".join(risk_review.blocking[:5]))
        else:
            satisfied.append("risk_review_passed")

        # 3. Valid multi-role human approval.
        record = self.registry.latest_valid(strategy, ACTION_PROMOTE_TO_LIVE, now)
        if record is None:
            reasons.append("no_valid_human_approval")
        else:
            missing = record.missing_roles
            if missing:
                reasons.append(
                    "approval_missing_roles:" + ",".join(r.value for r in missing))
            else:
                satisfied.append("human_approval_valid")

        # 4. Explicit out-of-band operator authorisation.
        if not self.env_authorized():
            reasons.append(f"{LIVE_AUTH_ENV_VAR}_not_set")
        else:
            satisfied.append("operator_env_authorization")

        # 5. System health and capital cap.
        if self.state.is_emergency_stopped():
            reasons.append("system_emergency_stopped")
        else:
            satisfied.append("system_not_emergency_stopped")

        if requested_capital <= 0:
            reasons.append("no_capital_cap_specified")
        elif self.max_capital_cap <= 0:
            reasons.append("no_platform_capital_cap_configured")
        elif requested_capital > self.max_capital_cap:
            reasons.append(
                f"requested_capital={requested_capital}>cap={self.max_capital_cap}")
        else:
            satisfied.append("capital_within_cap")

        authorized = len(reasons) == 0
        check = AuthorizationCheck(
            strategy=strategy, authorized=authorized,
            reasons=reasons, satisfied=satisfied, checked_at=now,
        )

        if authorized and record is not None:
            auth = LiveTradingAuthorization(
                strategy=strategy,
                approval_request_id=record.request_id,
                max_capital=requested_capital,
                issued_at=now,
                conditions=[
                    "kill switch remains armed at all times",
                    "authorization expires automatically and must be re-issued",
                    "any risk-engine veto or degradation alert revokes this grant",
                ],
            )
            self._issued[strategy] = auth
            check.authorization = auth
            log.warning("live_authorization_issued", strategy=strategy,
                        max_capital=requested_capital,
                        approval=record.request_id)
        else:
            log.info("live_authorization_denied", strategy=strategy,
                     reasons=reasons)
        return check

    # -------------------------------------------------------------- #
    def require_authorization(
        self, strategy: str, now: Optional[datetime] = None
    ) -> LiveTradingAuthorization:
        """Return a valid authorization or raise. Call before any live action."""
        auth = self._issued.get(strategy)
        if auth is None or not auth.is_valid(now):
            raise LiveAuthorizationError(
                f"no valid live-trading authorization for '{strategy}'; "
                "live trading remains disabled"
            )
        if not self.env_authorized():
            raise LiveAuthorizationError(
                f"{LIVE_AUTH_ENV_VAR} is not set; live trading remains disabled")
        if self.state.is_emergency_stopped():
            raise LiveAuthorizationError("system is emergency-stopped")
        return auth

    def revoke(self, strategy: str, reason: str) -> Optional[LiveTradingAuthorization]:
        auth = self._issued.get(strategy)
        if auth is not None:
            auth.revoke(reason)
        record = self.registry.latest_valid(strategy, ACTION_PROMOTE_TO_LIVE)
        if record is not None:
            self.registry.revoke(record.request_id, reason)
        return auth

    def revoke_all(self, reason: str) -> int:
        count = 0
        for strategy in list(self._issued):
            if not self._issued[strategy].revoked:
                self.revoke(strategy, reason)
                count += 1
        return count

    # -------------------------------------------------------------- #
    def posture(self) -> Dict[str, Any]:
        """Human-readable summary of the current live-trading posture."""
        mode = self.state.get_mode()
        return {
            "trading_mode": mode.value if hasattr(mode, "value") else str(mode),
            "live_trading_enabled": mode == TradingMode.LIVE,
            "env_authorization_present": self.env_authorized(),
            "platform_capital_cap": self.max_capital_cap,
            "active_authorizations": [
                a.to_dict() for a in self._issued.values() if a.is_valid()
            ],
            "pending_approvals": [
                r.to_dict() for r in self.registry.pending()
                if r.action == ACTION_PROMOTE_TO_LIVE
            ],
            "required_roles": [r.value for r in REQUIRED_ROLES],
        }
