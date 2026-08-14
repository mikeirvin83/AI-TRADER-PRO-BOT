"""Research router."""
from __future__ import annotations

from typing import List

from fastapi import APIRouter

from api.schemas import GenericResponse, HypothesisRequest
from research.hypothesis_manager import HypothesisManager

router = APIRouter(prefix="/research", tags=["research"])
_manager = HypothesisManager()


@router.post("/hypotheses", response_model=GenericResponse)
def create_hypothesis(req: HypothesisRequest) -> GenericResponse:
    result = _manager.create_hypothesis(
        title=req.title, description=req.description,
        rationale=req.rationale, success_criteria=req.success_criteria,
    )
    return GenericResponse(success=True, detail="created", data=result)


@router.get("/hypotheses", response_model=GenericResponse)
def list_hypotheses() -> GenericResponse:
    return GenericResponse(success=True, data={"hypotheses": _manager.get_hypotheses()})
