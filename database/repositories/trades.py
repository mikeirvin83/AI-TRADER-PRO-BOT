"""Trade repository."""
from __future__ import annotations

from typing import List

from sqlalchemy import select

from database.models import Trade
from database.repositories import BaseRepository


class TradeRepository(BaseRepository[Trade]):
    model = Trade

    def for_strategy(self, strategy_id) -> List[Trade]:
        return list(self.session.scalars(select(Trade).where(Trade.strategy_id == strategy_id)).all())

    def closed_trades(self, limit: int = 500) -> List[Trade]:
        stmt = (
            select(Trade)
            .where(Trade.exit_time.is_not(None))
            .order_by(Trade.exit_time.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())
