from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ApproveActionRequest:
    action_id: str
    note: str | None = None


@dataclass
class RejectActionRequest:
    action_id: str
    reason: str


@dataclass
class EditActionRequest:
    action_id: str
    preview: str | None = None
    subject: str | None = None
    body: str | None = None
