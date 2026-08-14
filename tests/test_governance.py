"""Tests for the Phase 12 governance layer.

These tests exist primarily to prove a *negative*: that no combination of
automated success can authorise live capital without explicit, unexpired,
multi-role human sign-off plus an out-of-band operator authorisation.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from core.system_state import get_system_state
from governance.approval_registry import (
    ApprovalRegistry,
    ApprovalStatus,
    Approver,
    ApproverRole,
)
from governance.live_authorization import (
    ACTION_PROMOTE_TO_LIVE,
    LIVE_AUTH_ENV_VAR,
    LiveAuthorizationError,
    LiveAuthorizationGate,
)
from governance.risk_review import ChecklistItem, RiskReviewChecklist

RISK = Approver("Dana Risk", ApproverRole.RISK_OFFICER)
OWNER = Approver("Sam Owner", ApproverRole.PORTFOLIO_OWNER)
OPS = Approver("Ops Bot Handler", ApproverRole.OPERATOR)
SYSTEM = Approver("automation", ApproverRole.SYSTEM)


def _full_evidence() -> dict:
    return {
        "all_gates_passed": True,
        "shadow_divergence_pct": 0.02,
        "max_divergence_pct": 0.10,
        "position_limits_defined": True,
        "kill_switch_tested": True,
        "drawdown_limits_configured": True,
        "open_degradation_alerts": [],
        "max_correlation": 0.3,
        "correlation_limit": 0.7,
    }


def _complete_review(strategy: str = "s") -> RiskReviewChecklist:
    cl = RiskReviewChecklist(strategy)
    for item in cl.manual_items:
        cl.attest(item.key, True, attested_by="Dana Risk")
    return cl


# ---------------------------------------------------------------- #
# Approval registry
# ---------------------------------------------------------------- #
def test_request_creates_pending_record():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE, requested_by="system")
    assert rec.status is ApprovalStatus.PENDING
    assert reg.get(rec.request_id) is rec
    assert reg.pending() == [rec]


def test_single_role_approval_is_not_enough():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE)
    reg.vote(rec.request_id, RISK, True)
    assert rec.status is ApprovalStatus.PENDING
    assert ApproverRole.PORTFOLIO_OWNER in rec.missing_roles
    assert reg.has_valid_approval("strat_a", ACTION_PROMOTE_TO_LIVE) is False


def test_quorum_of_required_roles_approves():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE)
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    assert rec.status is ApprovalStatus.APPROVED
    assert rec.missing_roles == []
    assert reg.has_valid_approval("strat_a", ACTION_PROMOTE_TO_LIVE) is True


def test_system_role_cannot_cast_an_approving_vote():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE)
    with pytest.raises(PermissionError):
        reg.vote(rec.request_id, SYSTEM, True)


def test_system_role_may_still_veto():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE)
    reg.vote(rec.request_id, SYSTEM, False, comment="degradation detected")
    assert rec.status is ApprovalStatus.REJECTED


def test_any_single_rejection_is_terminal():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE)
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, False, comment="not convinced")
    assert rec.status is ApprovalStatus.REJECTED
    with pytest.raises(ValueError):
        reg.vote(rec.request_id, OPS, True)


def test_duplicate_vote_from_same_person_rejected():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE)
    reg.vote(rec.request_id, RISK, True)
    with pytest.raises(ValueError, match="already voted"):
        reg.vote(rec.request_id, RISK, True)


def test_vote_on_unknown_request_raises():
    with pytest.raises(KeyError):
        ApprovalRegistry().vote("nope", RISK, True)


def test_expired_approval_is_not_valid():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE, ttl_hours=1)
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    later = datetime.now(timezone.utc) + timedelta(hours=5)
    assert rec.is_valid(later) is False
    assert reg.has_valid_approval("strat_a", ACTION_PROMOTE_TO_LIVE, later) is False


def test_expire_stale_transitions_records():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE, ttl_hours=1)
    later = datetime.now(timezone.utc) + timedelta(hours=3)
    assert reg.expire_stale(later) == 1
    assert rec.status is ApprovalStatus.EXPIRED


def test_voting_after_expiry_raises():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE, ttl_hours=1)
    later = datetime.now(timezone.utc) + timedelta(hours=3)
    with pytest.raises(ValueError, match="expired"):
        reg.vote(rec.request_id, RISK, True, now=later)


def test_revoke_invalidates_approval():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE)
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    reg.revoke(rec.request_id, "drawdown breach")
    assert rec.status is ApprovalStatus.REVOKED
    assert reg.has_valid_approval("strat_a", ACTION_PROMOTE_TO_LIVE) is False


def test_audit_log_is_appended():
    reg = ApprovalRegistry()
    rec = reg.request("strat_a", ACTION_PROMOTE_TO_LIVE)
    reg.vote(rec.request_id, RISK, True)
    events = [e["event"] for e in reg.audit_log]
    assert "requested" in events and "vote" in events


# ---------------------------------------------------------------- #
# Risk review checklist
# ---------------------------------------------------------------- #
def test_empty_checklist_fails_closed():
    result = RiskReviewChecklist("s").review({})
    assert result.passed is False
    assert result.blocking


def test_automated_items_evaluated_from_evidence():
    cl = RiskReviewChecklist("s")
    cl.evaluate_automated(_full_evidence())
    assert all(i.satisfied for i in cl.automated_items)


def test_manual_items_still_block_when_unattested():
    cl = RiskReviewChecklist("s")
    result = cl.review(_full_evidence())
    assert result.passed is False
    assert set(result.blocking) == {i.key for i in cl.manual_items}


def test_fully_attested_checklist_passes():
    cl = _complete_review()
    result = cl.review(_full_evidence())
    assert result.passed is True
    assert result.blocking == []


def test_wide_shadow_divergence_blocks_review():
    cl = _complete_review()
    evidence = _full_evidence()
    evidence["shadow_divergence_pct"] = 0.5
    result = cl.review(evidence)
    assert result.passed is False
    assert "shadow_divergence_within_limit" in result.blocking


def test_open_degradation_alert_blocks_review():
    cl = _complete_review()
    evidence = _full_evidence()
    evidence["open_degradation_alerts"] = ["sharpe_decay"]
    result = cl.review(evidence)
    assert result.passed is False
    assert "no_open_degradation_alerts" in result.blocking


def test_automated_item_cannot_be_manually_attested():
    cl = RiskReviewChecklist("s")
    with pytest.raises(ValueError, match="automated"):
        cl.attest("kill_switch_tested", True, "Dana Risk")


def test_attestation_requires_a_named_human():
    cl = RiskReviewChecklist("s")
    with pytest.raises(ValueError):
        cl.attest("rollback_plan_documented", True, "")


def test_predicate_error_fails_closed():
    item = ChecklistItem("boom", "raises", automated=True,
                         predicate=lambda e: 1 / 0)
    cl = RiskReviewChecklist("s", items=[item])
    result = cl.review({})
    assert result.passed is False
    assert item.satisfied is False
    assert "predicate_error" in item.note


def test_progress_tracks_answered_items():
    cl = RiskReviewChecklist("s")
    before = cl.progress()["answered"]
    cl.attest("rollback_plan_documented", True, "Sam Owner")
    assert cl.progress()["answered"] == before + 1


# ---------------------------------------------------------------- #
# Live authorization gate
# ---------------------------------------------------------------- #
def test_gate_denies_by_default():
    gate = LiveAuthorizationGate(registry=ApprovalRegistry())
    check = gate.evaluate("s")
    assert check.authorized is False
    assert check.authorization is None
    assert "no_validation_summary" in check.reasons


def test_gate_denies_without_env_authorization(monkeypatch):
    monkeypatch.delenv(LIVE_AUTH_ENV_VAR, raising=False)
    reg = ApprovalRegistry()
    gate = LiveAuthorizationGate(registry=reg, max_capital_cap=10_000)
    rec = gate.request_live_approval("s")
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    check = gate.evaluate(
        "s",
        validation_summary={"all_gates_passed": True, "current_stage": "APPROVAL"},
        risk_review=_complete_review().review(_full_evidence()),
        requested_capital=1_000,
    )
    assert check.authorized is False
    assert f"{LIVE_AUTH_ENV_VAR}_not_set" in check.reasons


def test_gate_denies_without_human_approval(monkeypatch):
    monkeypatch.setenv(LIVE_AUTH_ENV_VAR, "true")
    gate = LiveAuthorizationGate(registry=ApprovalRegistry(), max_capital_cap=10_000)
    check = gate.evaluate(
        "s",
        validation_summary={"all_gates_passed": True, "current_stage": "APPROVAL"},
        risk_review=_complete_review().review(_full_evidence()),
        requested_capital=1_000,
    )
    assert check.authorized is False
    assert "no_valid_human_approval" in check.reasons


def test_gate_denies_when_gates_not_passed(monkeypatch):
    monkeypatch.setenv(LIVE_AUTH_ENV_VAR, "true")
    reg = ApprovalRegistry()
    gate = LiveAuthorizationGate(registry=reg, max_capital_cap=10_000)
    rec = gate.request_live_approval("s")
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    check = gate.evaluate(
        "s",
        validation_summary={"all_gates_passed": False, "current_stage": "APPROVAL"},
        risk_review=_complete_review().review(_full_evidence()),
        requested_capital=1_000,
    )
    assert check.authorized is False
    assert "automated_gates_not_all_passed" in check.reasons


def test_gate_denies_when_capital_exceeds_cap(monkeypatch):
    monkeypatch.setenv(LIVE_AUTH_ENV_VAR, "true")
    reg = ApprovalRegistry()
    gate = LiveAuthorizationGate(registry=reg, max_capital_cap=1_000)
    rec = gate.request_live_approval("s")
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    check = gate.evaluate(
        "s",
        validation_summary={"all_gates_passed": True, "current_stage": "APPROVAL"},
        risk_review=_complete_review().review(_full_evidence()),
        requested_capital=50_000,
    )
    assert check.authorized is False
    assert any("requested_capital" in r for r in check.reasons)


def test_gate_denies_when_emergency_stopped(monkeypatch):
    monkeypatch.setenv(LIVE_AUTH_ENV_VAR, "true")
    get_system_state().engage_emergency_stop("test", actor="pytest")
    reg = ApprovalRegistry()
    gate = LiveAuthorizationGate(registry=reg, max_capital_cap=10_000)
    rec = gate.request_live_approval("s")
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    check = gate.evaluate(
        "s",
        validation_summary={"all_gates_passed": True, "current_stage": "APPROVAL"},
        risk_review=_complete_review().review(_full_evidence()),
        requested_capital=1_000,
    )
    assert check.authorized is False
    assert "system_emergency_stopped" in check.reasons


def test_gate_authorizes_only_when_every_condition_met(monkeypatch):
    monkeypatch.setenv(LIVE_AUTH_ENV_VAR, "true")
    reg = ApprovalRegistry()
    gate = LiveAuthorizationGate(registry=reg, max_capital_cap=10_000)
    rec = gate.request_live_approval("s")
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    check = gate.evaluate(
        "s",
        validation_summary={"all_gates_passed": True, "current_stage": "APPROVAL"},
        risk_review=_complete_review().review(_full_evidence()),
        requested_capital=1_000,
    )
    assert check.authorized is True
    assert check.authorization is not None
    assert check.authorization.max_capital == 1_000
    assert check.authorization.is_valid() is True
    assert check.authorization.conditions


def test_require_authorization_raises_when_absent():
    gate = LiveAuthorizationGate(registry=ApprovalRegistry())
    with pytest.raises(LiveAuthorizationError, match="remains disabled"):
        gate.require_authorization("s")


def test_require_authorization_raises_when_env_removed(monkeypatch):
    monkeypatch.setenv(LIVE_AUTH_ENV_VAR, "true")
    reg = ApprovalRegistry()
    gate = LiveAuthorizationGate(registry=reg, max_capital_cap=10_000)
    rec = gate.request_live_approval("s")
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    gate.evaluate(
        "s",
        validation_summary={"all_gates_passed": True, "current_stage": "APPROVAL"},
        risk_review=_complete_review().review(_full_evidence()),
        requested_capital=1_000,
    )
    assert gate.require_authorization("s") is not None
    monkeypatch.delenv(LIVE_AUTH_ENV_VAR, raising=False)
    with pytest.raises(LiveAuthorizationError):
        gate.require_authorization("s")


def test_authorization_expires(monkeypatch):
    monkeypatch.setenv(LIVE_AUTH_ENV_VAR, "true")
    reg = ApprovalRegistry()
    gate = LiveAuthorizationGate(registry=reg, max_capital_cap=10_000)
    rec = gate.request_live_approval("s")
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    check = gate.evaluate(
        "s",
        validation_summary={"all_gates_passed": True, "current_stage": "APPROVAL"},
        risk_review=_complete_review().review(_full_evidence()),
        requested_capital=1_000,
    )
    later = datetime.now(timezone.utc) + timedelta(hours=48)
    assert check.authorization.is_valid(later) is False
    with pytest.raises(LiveAuthorizationError):
        gate.require_authorization("s", now=later)


def test_revoke_kills_authorization_and_approval(monkeypatch):
    monkeypatch.setenv(LIVE_AUTH_ENV_VAR, "true")
    reg = ApprovalRegistry()
    gate = LiveAuthorizationGate(registry=reg, max_capital_cap=10_000)
    rec = gate.request_live_approval("s")
    reg.vote(rec.request_id, RISK, True)
    reg.vote(rec.request_id, OWNER, True)
    gate.evaluate(
        "s",
        validation_summary={"all_gates_passed": True, "current_stage": "APPROVAL"},
        risk_review=_complete_review().review(_full_evidence()),
        requested_capital=1_000,
    )
    gate.revoke("s", "risk veto")
    assert rec.status is ApprovalStatus.REVOKED
    with pytest.raises(LiveAuthorizationError):
        gate.require_authorization("s")


def test_env_authorized_requires_explicit_true(monkeypatch):
    for val in ("", "0", "false", "no", "maybe"):
        monkeypatch.setenv(LIVE_AUTH_ENV_VAR, val)
        assert LiveAuthorizationGate.env_authorized() is False
    for val in ("1", "true", "TRUE", "yes", "on"):
        monkeypatch.setenv(LIVE_AUTH_ENV_VAR, val)
        assert LiveAuthorizationGate.env_authorized() is True


def test_posture_reports_live_disabled_by_default(monkeypatch):
    monkeypatch.delenv(LIVE_AUTH_ENV_VAR, raising=False)
    gate = LiveAuthorizationGate(registry=ApprovalRegistry())
    p = gate.posture()
    assert p["live_trading_enabled"] is False
    assert p["env_authorization_present"] is False
    assert p["active_authorizations"] == []
