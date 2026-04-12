from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from tools import crm_tool


class _FrozenDateTime:
    @classmethod
    def now(cls, tz=None):
        assert tz is timezone.utc
        return datetime(2026, 4, 12, 12, 0, 0, tzinfo=timezone.utc)


def _reset() -> None:
    crm_tool._DEAL_STORE.clear()
    crm_tool._ACTIVITY_STORE.clear()
    crm_tool._IDEMPOTENCY_CACHE.clear()


def _assert_contract_shape(response: dict) -> None:
    assert set(response.keys()) == {
        "success",
        "operation",
        "deal_id",
        "record",
        "timeline",
        "write_result",
        "conflict_hints",
    }
    assert isinstance(response["record"], dict)
    assert isinstance(response["timeline"], list)
    assert isinstance(response["write_result"], dict)
    assert isinstance(response["conflict_hints"], dict)


def test_crm_tool_contracts_cover_read_write_and_timeline_limit(monkeypatch) -> None:
    monkeypatch.setattr(crm_tool, "datetime", _FrozenDateTime)
    monkeypatch.setattr(crm_tool, "uuid4", lambda: UUID("00000000-0000-0000-0000-00000000c001"))
    _reset()

    seed = crm_tool.fetch_deal_record(deal_id="deal-contract-1")
    write_1 = crm_tool.append_activity_log(
        deal_id="deal-contract-1",
        activity_type="agent_note",
        note="first",
        idempotency_key="k1",
        expected_version=1,
    )
    write_2 = crm_tool.update_deal_stage(
        deal_id="deal-contract-1",
        stage="negotiation",
        idempotency_key="k2",
        expected_version=2,
    )
    timeline = crm_tool.fetch_activity_timeline(deal_id="deal-contract-1", limit=1)

    for response in (seed, write_1, write_2, timeline):
        _assert_contract_shape(response)

    assert seed["record"]["record_id"] == "crm-deal-contract-1"
    assert write_1["success"] is True
    assert write_2["success"] is True
    assert timeline["operation"] == "fetch_activity_timeline"
    assert len(timeline["timeline"]) == 1
    assert timeline["timeline"][0]["event_type"] == "stage_update"


def test_crm_tool_conflict_resolution_simulation_with_latest_version_retry(monkeypatch) -> None:
    monkeypatch.setattr(crm_tool, "datetime", _FrozenDateTime)
    _reset()

    _ = crm_tool.fetch_deal_record(deal_id="deal-contract-conflict")
    conflict = crm_tool.append_activity_log(
        deal_id="deal-contract-conflict",
        activity_type="agent_note",
        note="stale write",
        idempotency_key="conflict-1",
        expected_version=99,
    )
    latest = crm_tool.fetch_deal_record(deal_id="deal-contract-conflict")
    resolved = crm_tool.append_activity_log(
        deal_id="deal-contract-conflict",
        activity_type="agent_note",
        note="resolved write",
        idempotency_key="conflict-2",
        expected_version=int(latest["record"]["version"]),
    )

    assert conflict["success"] is False
    assert conflict["write_result"]["status"] == "conflict"
    assert conflict["conflict_hints"]["resolution_required"] is True

    assert resolved["success"] is True
    assert resolved["write_result"]["status"] == "logged"
    assert resolved["conflict_hints"]["conflict_detected"] is False
