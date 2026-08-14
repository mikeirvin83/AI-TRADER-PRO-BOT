"""Strategy repository."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from database.models import Strategy
from database.repositories import BaseRepository


class StrategyRepository(BaseRepository[Strategy]):
    model = Strategy

    def get_by_name(self, name: str) -> Optional[Strategy]:
        return self.session.scalar(select(Strategy).where(Strategy.name == name))

    def by_status(self, status: str) -> List[Strategy]:
        return list(self.session.scalars(select(Strategy).where(Strategy.status == status)).all())
