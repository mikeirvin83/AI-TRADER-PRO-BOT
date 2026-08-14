"""Market data (OHLCV) repository."""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert

from database.models import MarketData
from database.repositories import BaseRepository


class MarketDataRepository(BaseRepository[MarketData]):
    model = MarketData

    def get_bars(
        self, symbol: str, timeframe: str, start: datetime, end: datetime
    ) -> List[MarketData]:
        stmt = (
            select(MarketData)
            .where(
                MarketData.symbol == symbol,
                MarketData.timeframe == timeframe,
                MarketData.timestamp >= start,
                MarketData.timestamp <= end,
            )
            .order_by(MarketData.timestamp.asc())
        )
        return list(self.session.scalars(stmt).all())

    def latest_timestamp(self, symbol: str, timeframe: str) -> Optional[datetime]:
        stmt = (
            select(MarketData.timestamp)
            .where(MarketData.symbol == symbol, MarketData.timeframe == timeframe)
            .order_by(MarketData.timestamp.desc())
            .limit(1)
        )
        return self.session.scalar(stmt)

    def bulk_upsert(self, rows: List[dict]) -> int:
        """Idempotent upsert on (symbol, timeframe, timestamp)."""
        if not rows:
            return 0
        stmt = pg_insert(MarketData).values(rows)
        update_cols = {
            c: stmt.excluded[c]
            for c in ["open", "high", "low", "close", "volume", "vwap", "trade_count",
                      "is_adjusted", "is_estimated", "data_quality"]
        }
        stmt = stmt.on_conflict_do_update(constraint="uq_bar", set_=update_cols)
        self.session.execute(stmt)
        return len(rows)
