"""Signals router."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter

from api.schemas import SignalResponse
from database.models import Signal
from database.session import session_scope

router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=List[SignalResponse])
def list_signals(limit: int = 50) -> List[SignalResponse]:
    from sqlalchemy import select

    out: List[SignalResponse] = []
    with session_scope() as s:
        stmt = select(Signal).order_by(Signal.created_at.desc()).limit(limit)
        for sig in s.scalars(stmt).all():
            out.append(SignalResponse(
                symbol=sig.symbol, direction=sig.direction,
                entry=float(sig.entry_price), stop=float(sig.stop_price),
                target=float(sig.target_price), score=sig.score,
                regime=sig.regime, expiration_time=sig.expiration_time,
            ))
    return out
