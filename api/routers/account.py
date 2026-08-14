"""Account router."""
from __future__ import annotations

from fastapi import APIRouter

from api.schemas import AccountResponse
from core.system_state import get_system_state
from market_data.alpaca_client import AlpacaClient

router = APIRouter(prefix="/account", tags=["account"])


@router.get("", response_model=AccountResponse)
def get_account() -> AccountResponse:
    st = get_system_state()
    client = AlpacaClient()
    if client.sdk_available:
        try:
            acct = client.get_account()
            return AccountResponse(
                equity=float(acct.get("equity", 0) or 0),
                cash=float(acct.get("cash", 0) or 0),
                buying_power=float(acct.get("buying_power", 0) or 0),
                mode=st.get_mode().value,
            )
        except Exception:  # noqa: BLE001
            pass
    # Fallback when broker not reachable — never fabricate real balances.
    return AccountResponse(equity=0.0, cash=0.0, buying_power=0.0, mode=st.get_mode().value)
