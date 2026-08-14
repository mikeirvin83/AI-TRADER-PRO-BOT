"""Regime persistence & retrieval."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import MarketRegimeRow


class RegimeHistory:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(self, symbol: str, regime: str, confidence: float,
               timeframe: str = "1Day", features: Optional[dict] = None) -> MarketRegimeRow:
        row = MarketRegimeRow(
            symbol=symbol, timeframe=timeframe, regime=regime,
            confidence=confidence, features=features or {},
            timestamp=datetime.now(timezone.utc),
        )
        self.session.add(row)
        self.session.flush()
        return row

    def latest(self, symbol: str) -> Optional[MarketRegimeRow]:
        stmt = (select(MarketRegimeRow).where(MarketRegimeRow.symbol == symbol)
                .order_by(MarketRegimeRow.timestamp.desc()).limit(1))
        return self.session.scalar(stmt)

    def history(self, symbol: str, limit: int = 100) -> List[MarketRegimeRow]:
        stmt = (select(MarketRegimeRow).where(MarketRegimeRow.symbol == symbol)
                .order_by(MarketRegimeRow.timestamp.desc()).limit(limit))
        return list(self.session.scalars(stmt).all())
