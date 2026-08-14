"""Hypothesis manager — HYP-YYYY-NNNNNN research ID system with DB-backed CRUD."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.constants import HypothesisStatus
from config.logging_config import get_logger
from database.models import ResearchHypothesis
from database.repositories.knowledge import HypothesisRepository
from database.session import session_scope

log = get_logger(__name__)


class HypothesisManager:
    """Create and track research hypotheses.

    IDs are of the form ``HYP-YYYY-NNNNNN`` where YYYY is the year and NNNNNN is a
    zero-padded monotonically increasing sequence within that year.
    """

    def generate_id(self, session=None) -> str:
        year = datetime.now(timezone.utc).year
        if session is not None:
            seq = HypothesisRepository(session).max_sequence_for_year(year) + 1
            return f"HYP-{year}-{seq:06d}"
        with session_scope() as s:
            seq = HypothesisRepository(s).max_sequence_for_year(year) + 1
            return f"HYP-{year}-{seq:06d}"

    def create_hypothesis(
        self,
        title: str,
        description: str = "",
        rationale: str = "",
        proposed_by: str = "quant_researcher",
        success_criteria: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        with session_scope() as s:
            repo = HypothesisRepository(s)
            hyp_id = self.generate_id(s)
            row = ResearchHypothesis(
                hyp_id=hyp_id, title=title, description=description,
                rationale=rationale, proposed_by=proposed_by,
                status=HypothesisStatus.PROPOSED.value,
                success_criteria=success_criteria or {},
            )
            repo.add(row)
            log.info("hypothesis_created", hyp_id=hyp_id, title=title)
            return {"hyp_id": hyp_id, "title": title, "status": row.status}

    def update_status(self, hyp_id: str, status: HypothesisStatus,
                      results: Optional[Dict[str, Any]] = None) -> bool:
        with session_scope() as s:
            repo = HypothesisRepository(s)
            row = repo.get_by_hyp_id(hyp_id)
            if row is None:
                return False
            row.status = status.value if isinstance(status, HypothesisStatus) else str(status)
            if results is not None:
                row.results = results
            log.info("hypothesis_updated", hyp_id=hyp_id, status=row.status)
            return True

    def get_hypotheses(self, status: Optional[HypothesisStatus] = None) -> List[Dict[str, Any]]:
        with session_scope() as s:
            repo = HypothesisRepository(s)
            rows = repo.by_status(status.value) if status else repo.list(limit=1000)
            return [{"hyp_id": r.hyp_id, "title": r.title, "status": r.status,
                     "results": r.results} for r in rows]
