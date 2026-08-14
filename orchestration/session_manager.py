"""Market session manager — schedules trading, reviews, and maintenance.

Manages the lifecycle of a trading session:
  - Pre-market: load data, run news scan, prepare strategies
  - Market open: start the decision loop
  - Market close: run daily review, persist state
  - Weekly: run weekly review at end of Friday session

All times are in US/Eastern (NYSE). This manager does NOT manage the
event loop itself — it provides the scheduling logic.
"""
from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from enum import Enum
from typing import Any, Dict, Optional

import pytz  # type: ignore

from config.constants import MARKET_TIMEZONE, NYSE_OPEN, NYSE_CLOSE, NYSE_PREMARKET_OPEN
from config.logging_config import get_logger

log = get_logger(__name__)

_ET = pytz.timezone(MARKET_TIMEZONE)


class SessionPhase(str, Enum):
    """Current phase of the trading session."""
    CLOSED = "CLOSED"           # Outside all trading hours
    PREMARKET = "PREMARKET"     # Pre-market scan window (4:00-9:30 ET)
    REGULAR = "REGULAR"         # Regular trading hours (9:30-16:00 ET)
    AFTERHOURS = "AFTERHOURS"   # Post-market (16:00-20:00 ET)
    REVIEW = "REVIEW"           # Daily review period (after market close)


class SessionManager:
    """Determines session phase and schedules key events."""

    def __init__(
        self,
        premarket_prep_minutes: int = 30,
        post_close_review_minutes: int = 30,
    ) -> None:
        self.premarket_prep = timedelta(minutes=premarket_prep_minutes)
        self.review_window = timedelta(minutes=post_close_review_minutes)
        self._last_daily_review: Optional[datetime] = None
        self._last_weekly_review: Optional[datetime] = None

    def current_phase(self, now: Optional[datetime] = None) -> SessionPhase:
        """Determine the current session phase."""
        now_et = self._to_et(now)
        t = now_et.time()

        if t < NYSE_PREMARKET_OPEN:
            return SessionPhase.CLOSED
        if t < NYSE_OPEN:
            return SessionPhase.PREMARKET
        if t < NYSE_CLOSE:
            return SessionPhase.REGULAR
        # Post-close review window
        review_end = (datetime.combine(now_et.date(), NYSE_CLOSE) +
                      self.review_window).time()
        if t < review_end:
            return SessionPhase.REVIEW
        after_close = time(20, 0)
        if t < after_close:
            return SessionPhase.AFTERHOURS
        return SessionPhase.CLOSED

    def is_trading_allowed(self, now: Optional[datetime] = None) -> bool:
        """True during regular hours only."""
        return self.current_phase(now) == SessionPhase.REGULAR

    def should_run_daily_review(self, now: Optional[datetime] = None) -> bool:
        """True when it's time for the daily review (just after market close)."""
        phase = self.current_phase(now)
        if phase != SessionPhase.REVIEW:
            return False
        today = self._to_et(now).date()
        if self._last_daily_review and self._last_daily_review.date() == today:
            return False  # Already ran today
        return True

    def mark_daily_review_done(self, at: Optional[datetime] = None) -> None:
        self._last_daily_review = at or datetime.now(timezone.utc)

    def should_run_weekly_review(self, now: Optional[datetime] = None) -> bool:
        """True on Friday after daily review."""
        now_et = self._to_et(now)
        if now_et.weekday() != 4:  # Friday
            return False
        phase = self.current_phase(now)
        if phase != SessionPhase.REVIEW:
            return False
        # Only if daily review already ran
        if not self._last_daily_review or self._last_daily_review.date() != now_et.date():
            return False
        if self._last_weekly_review and self._last_weekly_review.date() == now_et.date():
            return False
        return True

    def mark_weekly_review_done(self, at: Optional[datetime] = None) -> None:
        self._last_weekly_review = at or datetime.now(timezone.utc)

    def time_to_next_phase(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Calculate seconds until the next session phase transition."""
        now_et = self._to_et(now)
        t = now_et.time()
        today = now_et.date()

        boundaries = [
            (NYSE_PREMARKET_OPEN, SessionPhase.PREMARKET),
            (NYSE_OPEN, SessionPhase.REGULAR),
            (NYSE_CLOSE, SessionPhase.REVIEW),
            (time(20, 0), SessionPhase.CLOSED),
        ]

        for boundary_time, next_phase in boundaries:
            if t < boundary_time:
                target = _ET.localize(datetime.combine(today, boundary_time))
                delta = (target - now_et).total_seconds()
                return {
                    "next_phase": next_phase.value,
                    "seconds_until": max(0, delta),
                    "target_time": target.isoformat(),
                }

        # Past 20:00 — next is tomorrow's premarket
        tomorrow = today + timedelta(days=1)
        target = _ET.localize(datetime.combine(tomorrow, NYSE_PREMARKET_OPEN))
        delta = (target - now_et).total_seconds()
        return {
            "next_phase": SessionPhase.PREMARKET.value,
            "seconds_until": max(0, delta),
            "target_time": target.isoformat(),
        }

    def session_summary(self, now: Optional[datetime] = None) -> Dict[str, Any]:
        """Return a comprehensive session status."""
        phase = self.current_phase(now)
        next_info = self.time_to_next_phase(now)
        return {
            "phase": phase.value,
            "trading_allowed": phase == SessionPhase.REGULAR,
            "next_phase": next_info["next_phase"],
            "seconds_to_next": next_info["seconds_until"],
            "daily_review_pending": self.should_run_daily_review(now),
            "weekly_review_pending": self.should_run_weekly_review(now),
        }

    @staticmethod
    def _to_et(dt: Optional[datetime] = None) -> datetime:
        """Convert to US/Eastern, or get current time in ET."""
        if dt is None:
            return datetime.now(_ET)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(_ET)
