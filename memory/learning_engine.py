"""Controlled learning engine — every change is proposed, reviewed, then applied.

Nothing here mutates live strategy parameters automatically. Proposals are
persisted as LearningEvent rows and must be approved (human or governor agent)
before they take effect — consistent with the platform's safety constraints.
"""
from __future__ import annotations

from typing import Any, Dict, List

from config.logging_config import get_logger
from database.models import LearningEvent
from database.session import session_scope

log = get_logger(__name__)


class LearningEngine:
    def propose_change(self, event_type: str, description: str,
                       before: Dict[str, Any], after: Dict[str, Any]) -> str:
        with session_scope() as s:
            ev = LearningEvent(event_type=event_type, description=description,
                               before_state=before, after_state=after, approved=False)
            s.add(ev)
            s.flush()
            log.info("learning_change_proposed", event_type=event_type, id=str(ev.id))
            return str(ev.id)

    def approve_change(self, event_id: str, approved_by: str) -> bool:
        with session_scope() as s:
            ev = s.get(LearningEvent, event_id)
            if ev is None:
                return False
            ev.approved = True
            ev.approved_by = approved_by
            log.info("learning_change_approved", id=event_id, by=approved_by)
            return True

    def pending_changes(self) -> List[Dict[str, Any]]:
        from sqlalchemy import select

        with session_scope() as s:
            rows = s.scalars(select(LearningEvent).where(LearningEvent.approved.is_(False))).all()
            return [{"id": str(r.id), "event_type": r.event_type,
                     "description": r.description} for r in rows]
