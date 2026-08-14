"""Positions router."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter

from api.schemas import PositionResponse
from market_data.alpaca_client import AlpacaClient

router = APIRouter(prefix="/positions", tags=["positions"])


@router.get("", response_model=List[PositionResponse])
def list_positions() -> List[PositionResponse]:
    client = AlpacaClient()
    out: List[PositionResponse] = []
    if client.sdk_available:
        try:
            for p in client.get_positions():
                out.append(PositionResponse(
                    symbol=p.get("symbol", ""),
                    qty=float(p.get("qty", 0) or 0),
                    avg_entry_price=float(p.get("avg_entry_price", 0) or 0),
                    market_value=float(p.get("market_value", 0) or 0),
                    unrealized_pnl=float(p.get("unrealized_pl", 0) or 0),
                ))
        except Exception:  # noqa: BLE001
            pass
    return out
