"""Economic calendar & event-risk state."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional


@dataclass
class EconomicEventDTO:
    name: str
    event_time: datetime
    importance: str = "medium"


class EconomicCalendar:
    """Determines whether the system is in an elevated / blackout event window.

    Events must be supplied from a real provider; this class only reasons about
    timing risk and never invents events.
    """

    def __init__(self, blackout_minutes: int = 15, elevated_minutes: int = 60) -> None:
        self.blackout = timedelta(minutes=blackout_minutes)
        self.elevated = timedelta(minutes=elevated_minutes)
        self._events: List[EconomicEventDTO] = []

    def load(self, events: List[EconomicEventDTO]) -> None:
        self._events = sorted(events, key=lambda e: e.event_time)

    def risk_state(self, at: Optional[datetime] = None) -> str:
        now = at or datetime.now(timezone.utc)
        for ev in self._events:
            if ev.importance != "high":
                continue
            delta = abs((ev.event_time - now).total_seconds())
            if delta <= self.blackout.total_seconds():
                return "blackout"
            if delta <= self.elevated.total_seconds():
                return "elevated"
        return "normal"

    def next_high_impact(self, at: Optional[datetime] = None) -> Optional[EconomicEventDTO]:
        now = at or datetime.now(timezone.utc)
        upcoming = [e for e in self._events if e.importance == "high" and e.event_time >= now]
        return upcoming[0] if upcoming else None
