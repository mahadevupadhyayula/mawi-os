from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from tools import crm_tool, email_tool, sms_tool


class _FrozenDateTime:
    @classmethod
    def now(cls, tz=None):
        assert tz is timezone.utc
        return datetime(2026, 4, 12, 9, 30, 0, tzinfo=timezone.utc)


def test_send_email_response_shape_and_types(monkeypatch) -> None:
    monkeypatch.setattr(email_tool, "uuid4", lambda: UUID("00000000-0000-0000-0000-000000000111"))
    monkeypatch.setattr(email_tool, "datetime", _FrozenDateTime)

    result = email_tool.send_email(to_name="Jordan Lee", subject="Hello", body="A" * 180)

    assert set(result.keys()) == {
        "success",
        "message_id",
        "provider_status",
        "sent_at",
        "to_name",
        "subject",
        "body_preview",
    }
    assert isinstance(result["success"], bool)
    assert isinstance(result["message_id"], str)
    assert isinstance(result["provider_status"], str)
    assert isinstance(result["sent_at"], str)
    assert isinstance(result["to_name"], str)
    assert isinstance(result["subject"], str)
    assert isinstance(result["body_preview"], str)
    assert result["message_id"] == "00000000-0000-0000-0000-000000000111"
    assert result["sent_at"] == "2026-04-12T09:30:00+00:00"
    assert result["body_preview"] == "A" * 120


def test_update_crm_response_shape_and_types(monkeypatch) -> None:
    monkeypatch.setattr(crm_tool, "datetime", _FrozenDateTime)

    result = crm_tool.update_crm(deal_id="deal-42", note="Followed up", message_id="msg-7")

    assert set(result.keys()) == {
        "success",
        "deal_id",
        "record_id",
        "status",
        "updated_at",
        "note",
        "linked_message_id",
    }
    assert isinstance(result["success"], bool)
    assert isinstance(result["deal_id"], str)
    assert isinstance(result["record_id"], str)
    assert isinstance(result["status"], str)
    assert isinstance(result["updated_at"], str)
    assert isinstance(result["note"], str)
    assert isinstance(result["linked_message_id"], str)
    assert result["updated_at"] == "2026-04-12T09:30:00+00:00"
    assert result["record_id"] == "crm-deal-42"


def test_send_sms_response_shape_and_types(monkeypatch) -> None:
    monkeypatch.setattr(sms_tool, "uuid4", lambda: UUID("00000000-0000-0000-0000-000000000222"))
    monkeypatch.setattr(sms_tool, "datetime", _FrozenDateTime)

    result = sms_tool.send_sms(to_name="Taylor", body="B" * 161)

    assert set(result.keys()) == {
        "success",
        "sms_id",
        "provider_status",
        "sent_at",
        "to_name",
        "body_preview",
        "channel_metadata",
    }
    assert isinstance(result["success"], bool)
    assert isinstance(result["sms_id"], str)
    assert isinstance(result["provider_status"], str)
    assert isinstance(result["sent_at"], str)
    assert isinstance(result["to_name"], str)
    assert isinstance(result["body_preview"], str)
    assert isinstance(result["channel_metadata"], dict)
    assert result["sms_id"] == "00000000-0000-0000-0000-000000000222"
    assert result["sent_at"] == "2026-04-12T09:30:00+00:00"
    assert result["body_preview"] == "B" * 120

    metadata = result["channel_metadata"]
    assert set(metadata.keys()) == {"carrier", "segments", "delivery_window"}
    assert isinstance(metadata["carrier"], str)
    assert isinstance(metadata["segments"], int)
    assert isinstance(metadata["delivery_window"], str)
    assert metadata["segments"] == 2
