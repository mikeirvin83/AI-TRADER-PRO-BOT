"""Signal repository."""
from __future__ import annotations

from typing import List

from sqlalchemy import select

from database.models import Signal
from database.repositories import BaseRepository


class SignalRepository(BaseRepository[Signal]):
    model = Signal

    def recent_for_symbol(self, symbol: str, limit: int = 20) -> List[Signal]:
        stmt = (
            select(Signal)
            .where(Signal.symbol == symbol)
            .order_by(Signal.created_at.desc())
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def unacted(self) -> List[Signal]:
        return list(self.session.scalars(select(Signal).where(Signal.acted_on.is_(False))).all())
