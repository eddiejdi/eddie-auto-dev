#!/usr/bin/env python3
"""
Review Queue — Fila centralizada de commits aguardando aprovação

Padrão: Agent cria trabalho → commit em branch feature → fila de review
        ReviewAgent aprova → merge automático para main

Persistência: PostgreSQL (ou SQLite em dev)
"""
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from enum import Enum

logger = logging.getLogger(__name__)


class ReviewQueueItem(Enum):
    """Modelo de item na fila"""

    pass  # Será preenchido com dataclass


class ReviewQueue:
    """Gerenciador de fila de reviews"""

    def __init__(self, db_url: str = None):
        """
        Args:
            db_url: postgresql://user:pass@localhost/db ou sqlite:///local.db
        """
        
        self.db_url = db_url or "sqlite:///agent_data/review_queue.db"
        self.items: Dict[str, Dict[str, Any]] = (
            {}
        )  # Em memória para prototype; usar DB depois
        self._init_db()

    def _init_db(self):
        """Criar tabela se não existir"""
        if "sqlite" in self.db_url:
            import sqlite3

            conn = sqlite3.connect(self.db_url.replace("sqlite:///", ""))
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS review_queue (
                    id TEXT PRIMARY KEY,
                    commit_id TEXT NOT NULL,
                    branch TEXT NOT NULL,
                    author_agent TEXT NOT NULL,
                    diff TEXT NOT NULL,
                    files_changed TEXT NOT NULL,
                    status TEXT DEFAULT 'pending',
                    created_at TEXT,
                    reviewed_at TEXT,
                    review_result TEXT,
                    retry_count INT DEFAULT 0,
                    priority INT DEFAULT 0
                )
            """
            )
            conn.commit()
            conn.close()
            logger.info("✅ Review queue DB initialized")

    def submit_for_review(
        self,
        commit_id: str,
        branch: str,
        author_agent: str,
        diff: str,
        files_changed: List[str],
        priority: int = 0,
    ) -> str:
        """
        Submeter um commit para review.

        Returns:
            queue_id (para tracking)
        """
        import uuid

        queue_id = str(uuid.uuid4())
        item = {
            "queue_id": queue_id,
            "commit_id": commit_id,
            "branch": branch,
            "author_agent": author_agent,
            "diff": diff,
            "files_changed": json.dumps(files_changed),
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "reviewed_at": None,
            "review_result": None,
            "retry_count": 0,
            "priority": priority,
        }

        self.items[queue_id] = item
        logger.info(
            "📥 Commit %s submetido para review (queue_id=%s)", commit_id[:7], queue_id
        )

        # Persistir em DB se configurado
        if "sqlite" in self.db_url:
            self._db_insert(item)

        return queue_id

    def get_pending_items(self, limit: int = 5) -> List[Dict[str, Any]]:
        """Obter próximos items da fila (ordered by priority, priority DESC then created_at ASC)"""
        pending = [
            v
            for v in self.items.values()
            if v.get("status") in ("pending", "needs_retest")
        ]
        pending.sort(
            key=lambda x: (-x.get("priority", 0), x.get("created_at"))
        )  # ordered by priority DESC, then created_at ASC
        return pending[:limit]

    def update_status(
        self,
        queue_id: str,
        status: str,
        review_result: Optional[Dict] = None,
    ) -> bool:
        """
        Atualizar status de um item (pending → approved → merged ou rejected)
        """
        if queue_id not in self.items:
            logger.warning("❌ Queue item %s não encontrado", queue_id)
            return False

        self.items[queue_id]["status"] = status
        self.items[queue_id]["reviewed_at"] = datetime.now().isoformat()

        if review_result:
            self.items[queue_id]["review_result"] = json.dumps(review_result)

        logger.info("✏️  Queue item %s status updated to %s", queue_id[:8], status)

        # Persistir
        if "sqlite" in self.db_url:
            self._db_update(queue_id, status, review_result)

        return True

    def increment_retry(self, queue_id: str) -> int:
        """Incrementar contador de retry (máximo 3)"""
        if queue_id not in self.items:
            return 0

        self.items[queue_id]["retry_count"] = self.items[queue_id].get(
            "retry_count", 0
        ) + 1
        return self.items[queue_id]["retry_count"]

    def get_item(self, queue_id: str) -> Optional[Dict[str, Any]]:
        """Obter um item específico"""
        return self.items.get(queue_id)

    def get_stats(self) -> Dict[str, Any]:
        """Estatísticas da fila"""
        pending = sum(
            1 for v in self.items.values() if v.get("status") == "pending"
        )
        approved = sum(
            1 for v in self.items.values() if v.get("status") == "approved"
        )
        merged = sum(
            1 for v in self.items.values() if v.get("status") == "merged"
        )
        rejected = sum(
            1 for v in self.items.values() if v.get("status") == "rejected"
        )

        return {
            "total": len(self.items),
            "pending": pending,
            "approved": approved,
            "merged": merged,
            "rejected": rejected,
            "approval_rate": (
                approved / max(approved + rejected, 1) * 100 if (approved + rejected) > 0 else 0
            ),
        }

    def cleanup_old_items(self, days: int = 30):
        """Limpar items antigos (30 dias)"""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        to_delete = [
            qid
            for qid, item in self.items.items()
            if item.get("created_at", "") < cutoff and item.get("status") == "merged"
        ]

        for qid in to_delete:
            del self.items[qid]
            logger.info("🗑️  Cleaned up old queue item %s", qid[:8])

        return len(to_delete)

    # ═══════════════════════════════════════════════════════════════════════
    # DB helpers (SQLite for now, easily ported to Postgres)
    # ═══════════════════════════════════════════════════════════════════════

    def _db_insert(self, item: Dict):
        """Insert item into DB"""
        if "sqlite" not in self.db_url:
            return

        try:
            import sqlite3

            conn = sqlite3.connect(self.db_url.replace("sqlite:///", ""))
            conn.execute(
                """INSERT INTO review_queue 
                   (id, commit_id, branch, author_agent, diff, files_changed, 
                    status, created_at, priority)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    item["queue_id"],
                    item["commit_id"],
                    item["branch"],
                    item["author_agent"],
                    item["diff"],
                    item["files_changed"],
                    item["status"],
                    item["created_at"],
                    item["priority"],
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("DB insert error: %s", e)

    def _db_update(self, queue_id: str, status: str, review_result: Optional[Dict]):
        """Update item status in DB"""
        if "sqlite" not in self.db_url:
            return

        try:
            import sqlite3

            conn = sqlite3.connect(self.db_url.replace("sqlite:///", ""))
            conn.execute(
                """UPDATE review_queue 
                   SET status = ?, reviewed_at = ?, review_result = ?
                   WHERE id = ?""",
                (
                    status,
                    datetime.now().isoformat(),
                    json.dumps(review_result) if review_result else None,
                    queue_id,
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error("DB update error: %s", e)


# Singleton
_instance: Optional[ReviewQueue] = None


def get_review_queue(db_url: str = None) -> ReviewQueue:
    """Singleton do ReviewQueue"""
    global _instance
    if _instance is None:
        _instance = ReviewQueue(db_url)
    return _instance
