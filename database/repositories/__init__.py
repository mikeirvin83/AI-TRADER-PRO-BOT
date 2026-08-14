"""Repository layer — thin data-access objects over the ORM models."""
from __future__ import annotations

import uuid
from typing import Generic, List, Optional, Type, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from database.models import Base

T = TypeVar("T", bound=Base)


class BaseRepository(Generic[T]):
    """Generic CRUD repository bound to a single ORM model class."""

    model: Type[T]

    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, obj: T) -> T:
        self.session.add(obj)
        self.session.flush()
        return obj

    def get(self, id_: uuid.UUID | str) -> Optional[T]:
        return self.session.get(self.model, id_)

    def list(self, limit: int = 100, offset: int = 0) -> List[T]:
        stmt = select(self.model).limit(limit).offset(offset)
        return list(self.session.scalars(stmt).all())

    def delete(self, obj: T) -> None:
        self.session.delete(obj)
        self.session.flush()

    def count(self) -> int:
        from sqlalchemy import func

        return int(self.session.scalar(select(func.count()).select_from(self.model)) or 0)
