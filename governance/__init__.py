"""Governance layer — human approval gates for capital-at-risk decisions.

Nothing in this package can place an order. Its sole purpose is to make the
transition from shadow trading to live capital *impossible* without an explicit,
recorded, multi-party human authorisation that satisfies every automated gate
first.
"""
from governance.approval_registry import (
    ApprovalDecision,
    ApprovalRecord,
    ApprovalRegistry,
    ApprovalStatus,
    Approver,
    ApproverRole,
)
from governance.risk_review import (
    ChecklistItem,
    RiskReviewChecklist,
    RiskReviewResult,
)
from governance.live_authorization import (
    LiveAuthorizationError,
    LiveAuthorizationGate,
    LiveTradingAuthorization,
)

__all__ = [
    "ApprovalDecision",
    "ApprovalRecord",
    "ApprovalRegistry",
    "ApprovalStatus",
    "Approver",
    "ApproverRole",
    "ChecklistItem",
    "RiskReviewChecklist",
    "RiskReviewResult",
    "LiveAuthorizationError",
    "LiveAuthorizationGate",
    "LiveTradingAuthorization",
]
