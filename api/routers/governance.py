"""Governance router — human approval gates for capital-at-risk decisions.

These endpoints let a human operator open approval requests, cast role-scoped
votes, work through the risk review checklist and inspect the current
live-trading posture.

What these endpoints deliberately CANNOT do:
  * place, modify or cancel any order;
  * switch the system into LIVE mode;
  * approve on behalf of the automated system.

Even a fully approved request only produces a time-boxed, capital-capped
authorization object. Live trading additionally requires the out-of-band
``LIVE_TRADING_AUTHORIZED`` operator environment variable, which no API call can
set.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from governance.approval_registry import (
    Approver,
    ApproverRole,
    get_approval_registry,
)
from governance.live_authorization import (
    ACTION_PROMOTE_TO_LIVE,
    LiveAuthorizationGate,
)
from governance.risk_review import RiskReviewChecklist

router = APIRouter(prefix="/governance", tags=["governance"])

# One gate and one checklist store per process. The registry itself is a
# module-level singleton so the audit trail is shared.
_gate = LiveAuthorizationGate()
_checklists: Dict[str, RiskReviewChecklist] = {}


def _checklist(strategy: str) -> RiskReviewChecklist:
    if strategy not in _checklists:
        _checklists[strategy] = RiskReviewChecklist(strategy)
    return _checklists[strategy]


# ---------------------------------------------------------------- #
# Schemas
# ---------------------------------------------------------------- #
class ApprovalRequestBody(BaseModel):
    strategy: str
    requested_by: str = "operator"
    action: str = ACTION_PROMOTE_TO_LIVE
    context: Dict[str, Any] = Field(default_factory=dict)


class VoteBody(BaseModel):
    approver_name: str
    role: ApproverRole
    approved: bool
    comment: str = ""


class RevokeBody(BaseModel):
    reason: str
    actor: str = "operator"


class AttestBody(BaseModel):
    item_key: str
    satisfied: bool
    attested_by: str
    note: str = ""


class EvaluateBody(BaseModel):
    strategy: str
    requested_capital: float = 0.0
    validation_summary: Dict[str, Any] = Field(default_factory=dict)
    evidence: Dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------- #
# Approval requests
# ---------------------------------------------------------------- #
@router.get("/approvals")
def list_approvals(pending_only: bool = False) -> Dict[str, Any]:
    reg = get_approval_registry()
    records = reg.pending() if pending_only else reg.all_records()
    return {"count": len(records), "approvals": [r.to_dict() for r in records]}


@router.post("/approvals")
def create_approval(body: ApprovalRequestBody) -> Dict[str, Any]:
    reg = get_approval_registry()
    record = reg.request(
        subject=body.strategy,
        action=body.action,
        requested_by=body.requested_by,
        context=body.context,
    )
    return record.to_dict()


@router.get("/approvals/{request_id}")
def get_approval(request_id: str) -> Dict[str, Any]:
    record = get_approval_registry().get(request_id)
    if record is None:
        raise HTTPException(status_code=404, detail="approval request not found")
    return record.to_dict()


@router.post("/approvals/{request_id}/vote")
def vote(request_id: str, body: VoteBody) -> Dict[str, Any]:
    reg = get_approval_registry()
    approver = Approver(body.approver_name, body.role)
    try:
        record = reg.vote(request_id, approver, body.approved, body.comment)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return record.to_dict()


@router.post("/approvals/{request_id}/revoke")
def revoke_approval(request_id: str, body: RevokeBody) -> Dict[str, Any]:
    try:
        record = get_approval_registry().revoke(request_id, body.reason, body.actor)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return record.to_dict()


@router.get("/audit")
def audit_log() -> Dict[str, Any]:
    entries = get_approval_registry().audit_log
    return {"count": len(entries), "entries": entries}


# ---------------------------------------------------------------- #
# Risk review checklist
# ---------------------------------------------------------------- #
@router.get("/risk-review/{strategy}")
def get_risk_review(strategy: str) -> Dict[str, Any]:
    cl = _checklist(strategy)
    return {"progress": cl.progress(), "items": [i.to_dict() for i in cl.items]}


@router.post("/risk-review/{strategy}/attest")
def attest_item(strategy: str, body: AttestBody) -> Dict[str, Any]:
    cl = _checklist(strategy)
    try:
        item = cl.attest(body.item_key, body.satisfied, body.attested_by, body.note)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return item.to_dict()


@router.post("/risk-review/{strategy}/review")
def run_risk_review(strategy: str, evidence: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return _checklist(strategy).review(evidence or {}).to_dict()


# ---------------------------------------------------------------- #
# Live authorization posture
# ---------------------------------------------------------------- #
@router.get("/live-posture")
def live_posture() -> Dict[str, Any]:
    return _gate.posture()


@router.post("/live-authorization/evaluate")
def evaluate_live_authorization(body: EvaluateBody) -> Dict[str, Any]:
    """Evaluate the deny-by-default live authorization gate.

    Returns the exact list of unmet conditions. Never enables live trading.
    """
    review = _checklist(body.strategy).review(body.evidence)
    check = _gate.evaluate(
        strategy=body.strategy,
        validation_summary=body.validation_summary,
        risk_review=review,
        requested_capital=body.requested_capital,
    )
    result = check.to_dict()
    result["risk_review"] = review.to_dict()
    return result


@router.post("/live-authorization/{strategy}/revoke")
def revoke_live_authorization(strategy: str, body: RevokeBody) -> Dict[str, Any]:
    _gate.revoke(strategy, body.reason)
    return _gate.posture()
