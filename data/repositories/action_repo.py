from __future__ import annotations

from datetime import datetime, timezone

from context.models import ActionContext
from data.db_client import DBClient


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ActionRepository:
    def __init__(self, db: DBClient | None = None) -> None:
        self.db = db or DBClient()

    def upsert_action(self, run_id: str, deal_id: str, action: ActionContext) -> None:
        now = _now()
        with self.db.tx() as conn:
            conn.execute(
                """
                INSERT INTO actions (
                    action_id, run_id, deal_id, action_type, subject, preview, body_draft,
                    confidence, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(action_id) DO UPDATE SET
                    subject=excluded.subject,
                    preview=excluded.preview,
                    body_draft=excluded.body_draft,
                    confidence=excluded.confidence,
                    status=excluded.status,
                    updated_at=excluded.updated_at
                """,
                (
                    action.action_id,
                    run_id,
                    deal_id,
                    action.type,
                    action.subject,
                    action.preview,
                    action.body_draft,
                    action.confidence,
                    action.status,
                    now,
                    now,
                ),
            )

    def set_approved(self, action_id: str, approver: str) -> None:
        with self.db.tx() as conn:
            conn.execute(
                "UPDATE actions SET status='approved', approved_by=?, approved_at=?, updated_at=? WHERE action_id=?",
                (approver, _now(), _now(), action_id),
            )

    def set_rejected(self, action_id: str, approver: str, reason: str) -> None:
        with self.db.tx() as conn:
            conn.execute(
                "UPDATE actions SET status='rejected', rejected_by=?, rejected_at=?, rejection_reason=?, updated_at=? WHERE action_id=?",
                (approver, _now(), reason, _now(), action_id),
            )

    def set_edited(self, action_id: str, approver: str, preview: str | None, body_draft: str | None) -> None:
        with self.db.tx() as conn:
            conn.execute(
                """
                UPDATE actions
                SET status='pending_approval',
                    preview=COALESCE(?, preview),
                    body_draft=COALESCE(?, body_draft),
                    edited_by=?, edited_at=?, updated_at=?
                WHERE action_id=?
                """,
                (preview, body_draft, approver, _now(), _now(), action_id),
            )


    def get_action(self, action_id: str) -> dict | None:
        with self.db.tx() as conn:
            row = conn.execute("SELECT * FROM actions WHERE action_id=?", (action_id,)).fetchone()
        return dict(row) if row else None

    def list_actions(self, status: str | None = None) -> list[dict]:
        with self.db.tx() as conn:
            if status:
                rows = conn.execute("SELECT * FROM actions WHERE status=? ORDER BY updated_at DESC", (status,)).fetchall()
            else:
                rows = conn.execute("SELECT * FROM actions ORDER BY updated_at DESC").fetchall()
        return [dict(r) for r in rows]
