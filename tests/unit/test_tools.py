from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from tools import crm_tool, email_tool, sms_tool


class _FrozenDateTime:
    @classmethod
    def now(cls, tz=None):
        assert tz is timezone.utc
        return datetime(2026, 4, 12, 9, 30, 0, tzinfo=timezone.utc)


def _reset_crm_stores() -> None:
    crm_tool._DEAL_STORE.clear()
    crm_tool._ACTIVITY_STORE.clear()
    crm_tool._IDEMPOTENCY_CACHE.clear()


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
    monkeypatch.setattr(crm_tool, "uuid4", lambda: UUID("00000000-0000-0000-0000-000000000333"))
    _reset_crm_stores()

    result = crm_tool.update_crm(deal_id="deal-42", note="Followed up", message_id="msg-7")

    assert set(result.keys()) == {
        "success",
        "operation",
        "deal_id",
        "record",
        "timeline",
        "write_result",
        "conflict_hints",
    }
    assert result["success"] is True
    assert result["operation"] == "append_activity_log"
    assert result["deal_id"] == "deal-42"
    assert isinstance(result["record"], dict)
    assert isinstance(result["timeline"], list)
    assert isinstance(result["write_result"], dict)
    assert isinstance(result["conflict_hints"], dict)
    assert result["record"]["record_id"] == "crm-deal-42"
    assert result["record"]["last_modified"] == "2026-04-12T09:30:00+00:00"
    assert result["conflict_hints"] == {
        "version": 2,
        "last_modified": "2026-04-12T09:30:00+00:00",
        "conflict_detected": False,
        "resolution_required": False,
    }
    assert result["timeline"][0]["activity_id"] == "00000000-0000-0000-0000-000000000333"


def test_crm_writebacks_support_idempotency_and_conflict_hints(monkeypatch) -> None:
    monkeypatch.setattr(crm_tool, "datetime", _FrozenDateTime)
    monkeypatch.setattr(crm_tool, "uuid4", lambda: UUID("00000000-0000-0000-0000-000000000444"))
    _reset_crm_stores()

    first = crm_tool.update_deal_stage(
        deal_id="deal-99",
        stage="negotiation",
        idempotency_key="sync-1",
        expected_version=1,
    )
    second = crm_tool.update_deal_stage(
        deal_id="deal-99",
        stage="negotiation",
        idempotency_key="sync-1",
        expected_version=999,
    )

    assert first == second
    assert first["success"] is True
    assert first["conflict_hints"]["conflict_detected"] is False

    conflict = crm_tool.append_activity_log(
        deal_id="deal-99",
        activity_type="agent_note",
        note="Needs legal review",
        idempotency_key="sync-2",
        expected_version=1,
    )
    assert conflict["success"] is False
    assert conflict["write_result"]["status"] == "conflict"
    assert conflict["conflict_hints"]["conflict_detected"] is True
    assert conflict["conflict_hints"]["resolution_required"] is True


def test_fetch_crm_read_functions_return_normalized_schema(monkeypatch) -> None:
    monkeypatch.setattr(crm_tool, "datetime", _FrozenDateTime)
    _reset_crm_stores()

    record_response = crm_tool.fetch_deal_record(deal_id="deal-55")
    timeline_response = crm_tool.fetch_activity_timeline(deal_id="deal-55", limit=5)

    for result in (record_response, timeline_response):
        assert set(result.keys()) == {
            "success",
            "operation",
            "deal_id",
            "record",
            "timeline",
            "write_result",
            "conflict_hints",
        }
        assert result["conflict_hints"]["conflict_detected"] is False
        assert result["conflict_hints"]["resolution_required"] is False

    assert record_response["operation"] == "fetch_deal_record"
    assert timeline_response["operation"] == "fetch_activity_timeline"


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
