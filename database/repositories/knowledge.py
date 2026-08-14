"""Knowledge / research repositories."""
from __future__ import annotations

from typing import List, Optional

from sqlalchemy import select

from database.models import KnowledgeMemory, ResearchHypothesis
from database.repositories import BaseRepository


class KnowledgeRepository(BaseRepository[KnowledgeMemory]):
    model = KnowledgeMemory

    def get_by_key(self, key: str) -> Optional[KnowledgeMemory]:
        return self.session.scalar(select(KnowledgeMemory).where(KnowledgeMemory.key == key))


class HypothesisRepository(BaseRepository[ResearchHypothesis]):
    model = ResearchHypothesis

    def get_by_hyp_id(self, hyp_id: str) -> Optional[ResearchHypothesis]:
        return self.session.scalar(
            select(ResearchHypothesis).where(ResearchHypothesis.hyp_id == hyp_id)
        )

    def by_status(self, status: str) -> List[ResearchHypothesis]:
        return list(
            self.session.scalars(
                select(ResearchHypothesis).where(ResearchHypothesis.status == status)
            ).all()
        )

    def max_sequence_for_year(self, year: int) -> int:
        prefix = f"HYP-{year}-"
        rows = self.session.scalars(
            select(ResearchHypothesis.hyp_id).where(ResearchHypothesis.hyp_id.like(prefix + "%"))
        ).all()
        max_seq = 0
        for r in rows:
            try:
                max_seq = max(max_seq, int(r.split("-")[-1]))
            except (ValueError, IndexError):
                continue
        return max_seq
