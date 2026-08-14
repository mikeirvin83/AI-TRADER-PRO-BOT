"""Persistent AI knowledge base (DB-backed key/value with confidence)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from config.logging_config import get_logger
from database.models import KnowledgeMemory
from database.repositories.knowledge import KnowledgeRepository
from database.session import session_scope

log = get_logger(__name__)


class KnowledgeStore:
    def remember(self, key: str, content: Dict[str, Any], category: str = "general",
                 confidence: float = 0.5) -> None:
        with session_scope() as s:
            repo = KnowledgeRepository(s)
            row = repo.get_by_key(key)
            if row is None:
                repo.add(KnowledgeMemory(key=key, category=category, content=content,
                                         confidence=confidence, evidence_count=1,
                                         last_reinforced_at=datetime.now(timezone.utc)))
            else:
                row.content = content
                row.category = category
                row.confidence = confidence
                row.evidence_count += 1
                row.last_reinforced_at = datetime.now(timezone.utc)

    def recall(self, key: str) -> Optional[Dict[str, Any]]:
        with session_scope() as s:
            row = KnowledgeRepository(s).get_by_key(key)
            if row is None:
                return None
            return {"key": row.key, "category": row.category, "content": row.content,
                    "confidence": row.confidence, "evidence_count": row.evidence_count}

    def reinforce(self, key: str, delta: float = 0.05) -> None:
        with session_scope() as s:
            row = KnowledgeRepository(s).get_by_key(key)
            if row is not None:
                row.confidence = min(1.0, row.confidence + delta)
                row.evidence_count += 1
                row.last_reinforced_at = datetime.now(timezone.utc)
