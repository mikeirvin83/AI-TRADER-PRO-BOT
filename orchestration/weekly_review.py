"""Weekly strategy review routine."""
from __future__ import annotations

from typing import Any, Dict, List

from config.logging_config import get_logger
from database.models import Strategy
from database.session import session_scope

log = get_logger(__name__)


class WeeklyReview:
    def run(self) -> Dict[str, Any]:
        from sqlalchemy import select

        with session_scope() as s:
            strategies: List[Strategy] = list(s.scalars(select(Strategy)).all())
            by_status: Dict[str, int] = {}
            for st in strategies:
                by_status[st.status] = by_status.get(st.status, 0) + 1
            summary = {"n_strategies": len(strategies), "by_status": by_status}
        log.info("weekly_review", **summary)
        return summary
