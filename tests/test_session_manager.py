"""Tests for Phase 9 — Session Manager & Paper Trading Loop."""
from __future__ import annotations

from datetime import datetime, timezone

import pytz  # type: ignore
import pytest

from orchestration.session_manager import SessionManager, SessionPhase


_ET = pytz.timezone("America/New_York")


def _et(hour: int, minute: int = 0, weekday: int = 0) -> datetime:
    """Create a datetime in US/Eastern.

    weekday: 0=Monday .. 4=Friday
    Uses 2024-06-17 (Monday) as base and adds weekday offset.
    """
    base = datetime(2024, 6, 17 + weekday, hour, minute)
    return _ET.localize(base)


class TestSessionManager:
    def test_premarket_phase(self):
        mgr = SessionManager()
        # 5:00 AM ET on Monday
        phase = mgr.current_phase(_et(5, 0, 0))
        assert phase == SessionPhase.PREMARKET

    def test_regular_phase(self):
        mgr = SessionManager()
        # 10:00 AM ET on Monday
        phase = mgr.current_phase(_et(10, 0, 0))
        assert phase == SessionPhase.REGULAR

    def test_review_phase(self):
        mgr = SessionManager(post_close_review_minutes=30)
        # 4:15 PM ET on Monday (within 30-min review window after 4:00 close)
        phase = mgr.current_phase(_et(16, 15, 0))
        assert phase == SessionPhase.REVIEW

    def test_afterhours_phase(self):
        mgr = SessionManager(post_close_review_minutes=30)
        # 5:00 PM ET (after review window, before 8:00 PM)
        phase = mgr.current_phase(_et(17, 0, 0))
        assert phase == SessionPhase.AFTERHOURS

    def test_closed_phase_late(self):
        mgr = SessionManager()
        # 9:00 PM ET (after all hours)
        phase = mgr.current_phase(_et(21, 0, 0))
        assert phase == SessionPhase.CLOSED

    def test_closed_phase_early(self):
        mgr = SessionManager()
        # 3:00 AM ET (before premarket)
        phase = mgr.current_phase(_et(3, 0, 0))
        assert phase == SessionPhase.CLOSED

    def test_trading_allowed_only_regular(self):
        mgr = SessionManager()
        assert mgr.is_trading_allowed(_et(10, 0, 0))  # Regular
        assert not mgr.is_trading_allowed(_et(5, 0, 0))  # Premarket
        assert not mgr.is_trading_allowed(_et(17, 0, 0))  # Afterhours

    def test_daily_review_timing(self):
        mgr = SessionManager(post_close_review_minutes=30)
        # In review window
        assert mgr.should_run_daily_review(_et(16, 15, 0))
        # Not in review window
        assert not mgr.should_run_daily_review(_et(10, 0, 0))

    def test_daily_review_only_once(self):
        mgr = SessionManager(post_close_review_minutes=30)
        t = _et(16, 15, 0)
        assert mgr.should_run_daily_review(t)
        mgr.mark_daily_review_done(t)
        assert not mgr.should_run_daily_review(t)  # Already done

    def test_weekly_review_friday_only(self):
        mgr = SessionManager(post_close_review_minutes=30)
        # Monday review window — should not trigger weekly
        t_mon = _et(16, 15, 0)  # Monday
        mgr.mark_daily_review_done(t_mon)
        assert not mgr.should_run_weekly_review(t_mon)

        # Friday review window — should trigger weekly
        t_fri = _et(16, 15, 4)  # Friday
        mgr._last_daily_review = None  # Reset
        mgr.mark_daily_review_done(t_fri)
        assert mgr.should_run_weekly_review(t_fri)

    def test_weekly_review_only_once(self):
        mgr = SessionManager(post_close_review_minutes=30)
        t_fri = _et(16, 15, 4)
        mgr.mark_daily_review_done(t_fri)
        assert mgr.should_run_weekly_review(t_fri)
        mgr.mark_weekly_review_done(t_fri)
        assert not mgr.should_run_weekly_review(t_fri)

    def test_time_to_next_phase(self):
        mgr = SessionManager()
        # 8:00 AM — next should be REGULAR at 9:30
        info = mgr.time_to_next_phase(_et(8, 0, 0))
        assert info["next_phase"] == "REGULAR"
        assert info["seconds_until"] > 0

    def test_session_summary(self):
        mgr = SessionManager()
        summary = mgr.session_summary(_et(10, 0, 0))
        assert summary["phase"] == "REGULAR"
        assert summary["trading_allowed"] is True
        assert "next_phase" in summary


# ------------------------------------------------------------------ #
# Paper Trading Loop (unit tests, no live data)
# ------------------------------------------------------------------ #

class TestPaperTradingLoop:
    def test_loop_creation(self):
        from orchestration.paper_trading_loop import PaperTradingLoop
        loop = PaperTradingLoop(symbols=["SPY"], starting_cash=50_000)
        assert not loop._running
        assert loop.paper_engine.starting_cash == 50_000
        assert "SPY" in loop.symbols

    def test_loop_status(self):
        from orchestration.paper_trading_loop import PaperTradingLoop
        loop = PaperTradingLoop(symbols=["SPY"])
        status = loop.status()
        assert status["running"] is False
        assert status["cycle_count"] == 0
        assert "portfolio" in status
        assert "session" in status
        assert "risk" in status

    def test_loop_get_marks(self):
        from orchestration.paper_trading_loop import PaperTradingLoop
        loop = PaperTradingLoop()
        marks = loop._get_marks()
        assert isinstance(marks, dict)
        assert len(marks) == 0  # No positions yet
