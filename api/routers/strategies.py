"""Strategies router."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter

from api.schemas import StrategyResponse
from database.models import Strategy
from database.session import session_scope

router = APIRouter(prefix="/strategies", tags=["strategies"])


@router.get("", response_model=List[StrategyResponse])
def list_strategies() -> List[StrategyResponse]:
    from sqlalchemy import select

    out: List[StrategyResponse] = []
    with session_scope() as s:
        for st in s.scalars(select(Strategy)).all():
            out.append(StrategyResponse(
                name=st.name, category=st.category, status=st.status,
                version=st.current_version, allowed_regimes=st.allowed_regimes or [],
                min_signal_score=st.min_signal_score,
            ))
    return out
