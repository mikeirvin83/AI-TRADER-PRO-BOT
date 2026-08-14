"""Market clock & trading session detection.

Uses the standard US equity session calendar (regular + extended hours) and a
24/7 crypto session. Timezone-aware throughout (never naive datetimes).
"""
from __future__ import annotations

from datetime import datetime, time, timezone
from zoneinfo import ZoneInfo

from config.constants import (
    MARKET_TIMEZONE,
    NYSE_AFTERHOURS_CLOSE,
    NYSE_CLOSE,
    NYSE_OPEN,
    NYSE_PREMARKET_OPEN,
    AssetClass,
    MarketSession,
)

_MARKET_TZ = ZoneInfo(MARKET_TIMEZONE)


class MarketClock:
    """Determines the current market session for a given asset class."""

    def __init__(self, tz: ZoneInfo = _MARKET_TZ) -> None:
        self.tz = tz

    def now(self) -> datetime:
        return datetime.now(self.tz)

    @staticmethod
    def _is_weekend(dt: datetime) -> bool:
        return dt.weekday() >= 5  # 5=Sat, 6=Sun

    def session(
        self, asset_class: AssetClass = AssetClass.EQUITY, at: datetime | None = None
    ) -> MarketSession:
        """Return the market session for the given asset class and time."""
        dt = (at or self.now()).astimezone(self.tz)

        if asset_class == AssetClass.CRYPTO:
            return MarketSession.REGULAR  # crypto is 24/7

        if self._is_weekend(dt):
            return MarketSession.CLOSED

        t = dt.time()
        if NYSE_OPEN <= t < NYSE_CLOSE:
            return MarketSession.REGULAR
        if NYSE_PREMARKET_OPEN <= t < NYSE_OPEN:
            return MarketSession.PREMARKET
        if NYSE_CLOSE <= t < NYSE_AFTERHOURS_CLOSE:
            return MarketSession.AFTERHOURS
        return MarketSession.CLOSED

    def is_market_open(
        self, asset_class: AssetClass = AssetClass.EQUITY, at: datetime | None = None
    ) -> bool:
        """Regular-session open check (extended hours count as closed here)."""
        return self.session(asset_class, at) == MarketSession.REGULAR

    def seconds_to_open(self, at: datetime | None = None) -> float:
        """Seconds until the next regular equity open (0 if already open)."""
        dt = (at or self.now()).astimezone(self.tz)
        if self.is_market_open(AssetClass.EQUITY, dt):
            return 0.0
        open_today = dt.replace(
            hour=NYSE_OPEN.hour, minute=NYSE_OPEN.minute, second=0, microsecond=0
        )
        target = open_today if dt < open_today and not self._is_weekend(dt) else None
        if target is None:
            # advance to next weekday open
            day = dt
            while True:
                day = day.replace(hour=NYSE_OPEN.hour, minute=NYSE_OPEN.minute, second=0, microsecond=0)
                from datetime import timedelta

                day = day + timedelta(days=1)
                if day.weekday() < 5:
                    target = day
                    break
        return max(0.0, (target - dt).total_seconds())


def utc_now() -> datetime:
    """Convenience: timezone-aware UTC now."""
    return datetime.now(timezone.utc)


_clock = MarketClock()


def get_clock() -> MarketClock:
    return _clock
