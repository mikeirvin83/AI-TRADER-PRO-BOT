"""Human approval registry (Phase 12).

An append-only, auditable ledger of approval requests and human decisions. Used
by the APPROVAL promotion stage and by the live-authorization gate.

Design rules:
  * Records are append-only. A decision is never overwritten; superseding a
    decision creates a new record referencing the old one.
  * Approvals are role-scoped and *quorum*-based: a single person can never
    unilaterally authorise capital at risk.
  * Approvals expire. A stale approval is treated as absent.
  * Self-approval by the automated system is structurally impossible: the
    ``SYSTEM`` role cannot cast an approving vote.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger

log = get_logger(__name__)

#: Default lifetime of an approval before it must be re-obtained.
DEFAULT_APPROVAL_TTL_HOURS = 72


class ApproverRole(str, Enum):
    """Roles that may participate in an approval."""
    RISK_OFFICER = "RISK_OFFICER"
    PORTFOLIO_OWNER = "PORTFOLIO_OWNER"
    OPERATOR = "OPERATOR"
    SYSTEM = "SYSTEM"  # may request and may VETO, may never APPROVE


#: Roles whose sign-off is mandatory for any live-capital authorisation.
REQUIRED_ROLES = (ApproverRole.RISK_OFFICER, ApproverRole.PORTFOLIO_OWNER)


class ApprovalStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"


@dataclass(frozen=True)
class Approver:
    """A human authorised to vote on approval requests."""
    name: str
    role: ApproverRole

    @property
    def can_approve(self) -> bool:
        return self.role is not ApproverRole.SYSTEM


@dataclass(frozen=True)
class ApprovalDecision:
    """An immutable individual vote."""
    approver: Approver
    approved: bool
    comment: str = ""
    decided_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approver": self.approver.name,
            "role": self.approver.role.value,
            "approved": self.approved,
            "comment": self.comment,
            "decided_at": self.decided_at.isoformat(),
        }


@dataclass
class ApprovalRecord:
    """An approval request plus every vote cast against it."""
    request_id: str
    subject: str                     # e.g. strategy name
    action: str                      # e.g. "PROMOTE_TO_LIVE"
    requested_by: str
    context: Dict[str, Any] = field(default_factory=dict)
    decisions: List[ApprovalDecision] = field(default_factory=list)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None
    ttl_hours: int = DEFAULT_APPROVAL_TTL_HOURS
    supersedes: Optional[str] = None
    revocation_reason: str = ""

    # -------------------------------------------------------------- #
    @property
    def approving_roles(self) -> set:
        return {d.approver.role for d in self.decisions if d.approved}

    @property
    def rejecting_decisions(self) -> List[ApprovalDecision]:
        return [d for d in self.decisions if not d.approved]

    @property
    def missing_roles(self) -> List[ApproverRole]:
        return [r for r in REQUIRED_ROLES if r not in self.approving_roles]

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        now = now or datetime.now(timezone.utc)
        anchor = self.resolved_at or self.created_at
        return now > anchor + timedelta(hours=self.ttl_hours)

    def is_valid(self, now: Optional[datetime] = None) -> bool:
        """True only if fully approved, unexpired and unrevoked."""
        return self.status is ApprovalStatus.APPROVED and not self.is_expired(now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "subject": self.subject,
            "action": self.action,
            "requested_by": self.requested_by,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "ttl_hours": self.ttl_hours,
            "decisions": [d.to_dict() for d in self.decisions],
            "missing_roles": [r.value for r in self.missing_roles],
            "supersedes": self.supersedes,
            "revocation_reason": self.revocation_reason,
            "context": dict(self.context),
        }


class ApprovalRegistry:
    """Append-only ledger of approval requests."""

    def __init__(self) -> None:
        self._records: Dict[str, ApprovalRecord] = {}
        self._order: List[str] = []
        self._audit: List[Dict[str, Any]] = []

    # -------------------------------------------------------------- #
    def _log_audit(self, event: str, **fields: Any) -> None:
        entry = {"event": event, "at": datetime.now(timezone.utc).isoformat()}
        entry.update(fields)
        self._audit.append(entry)
        log.info(f"approval_{event}", **fields)

    @property
    def audit_log(self) -> List[Dict[str, Any]]:
        return list(self._audit)

    # -------------------------------------------------------------- #
    def request(
        self,
        subject: str,
        action: str,
        requested_by: str = "system",
        context: Optional[Dict[str, Any]] = None,
        ttl_hours: int = DEFAULT_APPROVAL_TTL_HOURS,
        supersedes: Optional[str] = None,
    ) -> ApprovalRecord:
        record = ApprovalRecord(
            request_id=uuid.uuid4().hex[:12],
            subject=subject,
            action=action,
            requested_by=requested_by,
            context=dict(context or {}),
            ttl_hours=ttl_hours,
            supersedes=supersedes,
        )
        self._records[record.request_id] = record
        self._order.append(record.request_id)
        self._log_audit("requested", request_id=record.request_id,
                        subject=subject, action=action, requested_by=requested_by)
        return record

    def get(self, request_id: str) -> Optional[ApprovalRecord]:
        return self._records.get(request_id)

    def all_records(self) -> List[ApprovalRecord]:
        return [self._records[i] for i in self._order]

    def pending(self) -> List[ApprovalRecord]:
        return [r for r in self.all_records() if r.status is ApprovalStatus.PENDING]

    # -------------------------------------------------------------- #
    def vote(
        self,
        request_id: str,
        approver: Approver,
        approved: bool,
        comment: str = "",
        now: Optional[datetime] = None,
    ) -> ApprovalRecord:
        """Cast a single vote. Raises on invalid or duplicate votes."""
        now = now or datetime.now(timezone.utc)
        record = self._records.get(request_id)
        if record is None:
            raise KeyError(f"unknown approval request: {request_id}")

        if record.status is not ApprovalStatus.PENDING:
            raise ValueError(
                f"request {request_id} is {record.status.value}; no further votes allowed")

        if record.is_expired(now):
            record.status = ApprovalStatus.EXPIRED
            record.resolved_at = now
            self._log_audit("expired", request_id=request_id)
            raise ValueError(f"request {request_id} has expired")

        if approved and not approver.can_approve:
            raise PermissionError(
                f"role {approver.role.value} may not cast an approving vote")

        if any(d.approver.name == approver.name for d in record.decisions):
            raise ValueError(f"{approver.name} has already voted on {request_id}")

        decision = ApprovalDecision(approver, approved, comment, decided_at=now)
        record.decisions.append(decision)
        self._log_audit("vote", request_id=request_id, approver=approver.name,
                        role=approver.role.value, approved=approved)

        # Any single rejection is terminal — fail closed.
        if not approved:
            record.status = ApprovalStatus.REJECTED
            record.resolved_at = now
            self._log_audit("rejected", request_id=request_id,
                            approver=approver.name, comment=comment)
            return record

        if not record.missing_roles:
            record.status = ApprovalStatus.APPROVED
            record.resolved_at = now
            self._log_audit("approved", request_id=request_id,
                            roles=[r.value for r in sorted(
                                record.approving_roles, key=lambda x: x.value)])
        return record

    # -------------------------------------------------------------- #
    def revoke(
        self,
        request_id: str,
        reason: str,
        actor: str = "operator",
        now: Optional[datetime] = None,
    ) -> ApprovalRecord:
        """Revoke a previously granted approval. Always permitted."""
        now = now or datetime.now(timezone.utc)
        record = self._records.get(request_id)
        if record is None:
            raise KeyError(f"unknown approval request: {request_id}")
        record.status = ApprovalStatus.REVOKED
        record.revocation_reason = reason
        record.resolved_at = now
        self._log_audit("revoked", request_id=request_id, actor=actor, reason=reason)
        return record

    def expire_stale(self, now: Optional[datetime] = None) -> int:
        now = now or datetime.now(timezone.utc)
        count = 0
        for record in self.all_records():
            if record.status in (ApprovalStatus.PENDING, ApprovalStatus.APPROVED) \
                    and record.is_expired(now):
                record.status = ApprovalStatus.EXPIRED
                record.resolved_at = record.resolved_at or now
                count += 1
                self._log_audit("expired", request_id=record.request_id)
        return count

    # -------------------------------------------------------------- #
    def latest_valid(
        self,
        subject: str,
        action: str,
        now: Optional[datetime] = None,
    ) -> Optional[ApprovalRecord]:
        """Most recent still-valid approval for a (subject, action) pair."""
        for record in reversed(self.all_records()):
            if record.subject == subject and record.action == action \
                    and record.is_valid(now):
                return record
        return None

    def has_valid_approval(
        self, subject: str, action: str, now: Optional[datetime] = None
    ) -> bool:
        return self.latest_valid(subject, action, now) is not None


_registry: Optional[ApprovalRegistry] = None


def get_approval_registry() -> ApprovalRegistry:
    global _registry
    if _registry is None:
        _registry = ApprovalRegistry()
    return _registry
