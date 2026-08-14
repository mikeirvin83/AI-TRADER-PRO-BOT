"""System router — kill switch and trading mode control."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.schemas import GenericResponse, KillSwitchRequest, ModeChangeRequest, ModeResponse
from core.system_state import IllegalTransitionError, get_system_state

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/mode", response_model=ModeResponse)
def get_mode() -> ModeResponse:
    st = get_system_state()
    return ModeResponse(mode=st.get_mode().value, trading_allowed=st.is_trading_allowed(),
                        emergency_stopped=st.is_emergency_stopped())


@router.post("/mode", response_model=ModeResponse)
def set_mode(req: ModeChangeRequest) -> ModeResponse:
    st = get_system_state()
    try:
        st.transition_to(req.mode, req.reason, actor=req.actor)
    except IllegalTransitionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ModeResponse(mode=st.get_mode().value, trading_allowed=st.is_trading_allowed(),
                        emergency_stopped=st.is_emergency_stopped())


@router.post("/kill", response_model=ModeResponse)
def kill_switch(req: KillSwitchRequest) -> ModeResponse:
    st = get_system_state()
    st.engage_emergency_stop(req.reason, actor=req.actor)
    return ModeResponse(mode=st.get_mode().value, trading_allowed=st.is_trading_allowed(),
                        emergency_stopped=st.is_emergency_stopped())


@router.post("/reset", response_model=ModeResponse)
def reset_kill_switch(req: KillSwitchRequest) -> ModeResponse:
    st = get_system_state()
    st.reset_emergency_stop(req.reason, actor=req.actor)
    return ModeResponse(mode=st.get_mode().value, trading_allowed=st.is_trading_allowed(),
                        emergency_stopped=st.is_emergency_stopped())


@router.get("/history", response_model=GenericResponse)
def mode_history() -> GenericResponse:
    st = get_system_state()
    hist = [{"from": h.from_mode.value, "to": h.to_mode.value, "reason": h.reason,
             "actor": h.actor, "timestamp": h.timestamp.isoformat()} for h in st.get_history()]
    return GenericResponse(success=True, data={"history": hist})
