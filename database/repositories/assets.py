"""Asset repository."""
from __future__ import annotations

from typing import Optional

from sqlalchemy import select

from database.models import Asset
from database.repositories import BaseRepository


class AssetRepository(BaseRepository[Asset]):
    model = Asset

    def get_by_symbol(self, symbol: str) -> Optional[Asset]:
        return self.session.scalar(select(Asset).where(Asset.symbol == symbol))

    def upsert(self, symbol: str, **fields) -> Asset:
        obj = self.get_by_symbol(symbol)
        if obj is None:
            obj = Asset(symbol=symbol, **fields)
            self.add(obj)
        else:
            for k, v in fields.items():
                setattr(obj, k, v)
            self.session.flush()
        return obj
