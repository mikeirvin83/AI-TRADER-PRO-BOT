"""Order repository."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from database.models import Order
from database.repositories import BaseRepository


class OrderRepository(BaseRepository[Order]):
    model = Order

    def get_by_broker_id(self, broker_order_id: str) -> Optional[Order]:
        return self.session.scalar(
            select(Order).where(Order.broker_order_id == broker_order_id)
        )

    def open_orders(self, symbol: Optional[str] = None) -> List[Order]:
        stmt = select(Order).where(
            Order.status.in_(["PENDING", "SUBMITTED", "PARTIALLY_FILLED"])
        )
        if symbol:
            stmt = stmt.where(Order.symbol == symbol)
        return list(self.session.scalars(stmt).all())

    def pending_for(self, symbol: str, side: str) -> List[Order]:
        stmt = select(Order).where(
            Order.symbol == symbol,
            Order.side == side,
            Order.status.in_(["PENDING", "SUBMITTED", "PARTIALLY_FILLED"]),
        )
        return list(self.session.scalars(stmt).all())
