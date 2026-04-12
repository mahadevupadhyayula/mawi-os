"""
Purpose:
Tool integration module `crm_tool` for external side effects used by workflows.

Technical Details:
Wraps provider behavior behind stable interfaces and returns structured execution metadata for deterministic state updates.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# Simulated in-memory persistence for local runs/tests.
_DEAL_STORE: Dict[str, Dict[str, Any]] = {}
_ACTIVITY_STORE: Dict[str, List[Dict[str, Any]]] = {}
_IDEMPOTENCY_CACHE: Dict[str, Dict[str, Any]] = {}


def _seed_deal_record(deal_id: str) -> Dict[str, Any]:
    now = _utcnow_iso()
    return {
        "deal_id": deal_id,
        "record_id": f"crm-{deal_id}",
        "stage": "proposal",
        "version": 1,
        "last_modified": now,
        "owner": "revops-simulated",
    }


def _normalize_conflict_hints(
    *,
    record: Dict[str, Any],
    expected_version: Optional[int],
) -> Dict[str, Any]:
    current_version = int(record["version"])
    conflict_detected = expected_version is not None and expected_version != current_version
    return {
        "version": current_version,
        "last_modified": record["last_modified"],
        "conflict_detected": conflict_detected,
        "resolution_required": conflict_detected,
    }


def _normalize_response(
    *,
    success: bool,
    operation: str,
    deal_id: str,
    record: Dict[str, Any],
    timeline: Optional[List[Dict[str, Any]]] = None,
    write_result: Optional[Dict[str, Any]] = None,
    conflict_hints: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    response: Dict[str, Any] = {
        "success": success,
        "operation": operation,
        "deal_id": deal_id,
        "record": deepcopy(record),
        "timeline": deepcopy(timeline) if timeline is not None else [],
        "write_result": deepcopy(write_result) if write_result is not None else {},
        "conflict_hints": deepcopy(conflict_hints) if conflict_hints is not None else _normalize_conflict_hints(record=record, expected_version=None),
    }
    return response


def _get_or_create_record(deal_id: str) -> Dict[str, Any]:
    record = _DEAL_STORE.get(deal_id)
    if record is None:
        record = _seed_deal_record(deal_id)
        _DEAL_STORE[deal_id] = record
    _ACTIVITY_STORE.setdefault(deal_id, [])
    return record


def fetch_deal_record(*, deal_id: str) -> Dict[str, Any]:
    """Read a CRM deal record without invoking any external API."""
    record = _get_or_create_record(deal_id)
    return _normalize_response(
        success=True,
        operation="fetch_deal_record",
        deal_id=deal_id,
        record=record,
    )


def fetch_activity_timeline(*, deal_id: str, limit: int = 25) -> Dict[str, Any]:
    """Read recent activity timeline entries for sync workflows."""
    record = _get_or_create_record(deal_id)
    timeline = list(reversed(_ACTIVITY_STORE.get(deal_id, [])))
    bounded_timeline = timeline[: max(0, limit)]
    return _normalize_response(
        success=True,
        operation="fetch_activity_timeline",
        deal_id=deal_id,
        record=record,
        timeline=bounded_timeline,
    )


def update_deal_stage(
    *,
    deal_id: str,
    stage: str,
    idempotency_key: str,
    expected_version: Optional[int] = None,
) -> Dict[str, Any]:
    """Write back a stage update with idempotency and sync conflict hints."""
    idempotency_cache_key = f"stage:{deal_id}:{idempotency_key}"
    cached = _IDEMPOTENCY_CACHE.get(idempotency_cache_key)
    if cached is not None:
        return deepcopy(cached)

    record = _get_or_create_record(deal_id)
    conflict_hints = _normalize_conflict_hints(record=record, expected_version=expected_version)
    if conflict_hints["conflict_detected"]:
        result = _normalize_response(
            success=False,
            operation="update_deal_stage",
            deal_id=deal_id,
            record=record,
            write_result={
                "status": "conflict",
                "idempotency_key": idempotency_key,
                "requested_stage": stage,
            },
            conflict_hints=conflict_hints,
        )
        _IDEMPOTENCY_CACHE[idempotency_cache_key] = deepcopy(result)
        return result

    now = _utcnow_iso()
    prior_stage = record["stage"]
    record["stage"] = stage
    record["version"] = int(record["version"]) + 1
    record["last_modified"] = now

    activity_entry = {
        "activity_id": str(uuid4()),
        "event_type": "stage_update",
        "created_at": now,
        "details": {
            "from_stage": prior_stage,
            "to_stage": stage,
            "idempotency_key": idempotency_key,
        },
    }
    _ACTIVITY_STORE[deal_id].append(activity_entry)

    result = _normalize_response(
        success=True,
        operation="update_deal_stage",
        deal_id=deal_id,
        record=record,
        timeline=[activity_entry],
        write_result={
            "status": "updated",
            "idempotency_key": idempotency_key,
            "stage": stage,
        },
        conflict_hints=_normalize_conflict_hints(record=record, expected_version=None),
    )
    _IDEMPOTENCY_CACHE[idempotency_cache_key] = deepcopy(result)
    return result


def append_activity_log(
    *,
    deal_id: str,
    activity_type: str,
    note: str,
    idempotency_key: str,
    expected_version: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Write back an activity entry with idempotency and conflict hints."""
    idempotency_cache_key = f"activity:{deal_id}:{idempotency_key}"
    cached = _IDEMPOTENCY_CACHE.get(idempotency_cache_key)
    if cached is not None:
        return deepcopy(cached)

    record = _get_or_create_record(deal_id)
    conflict_hints = _normalize_conflict_hints(record=record, expected_version=expected_version)
    if conflict_hints["conflict_detected"]:
        result = _normalize_response(
            success=False,
            operation="append_activity_log",
            deal_id=deal_id,
            record=record,
            write_result={
                "status": "conflict",
                "idempotency_key": idempotency_key,
                "activity_type": activity_type,
            },
            conflict_hints=conflict_hints,
        )
        _IDEMPOTENCY_CACHE[idempotency_cache_key] = deepcopy(result)
        return result

    now = _utcnow_iso()
    activity_entry = {
        "activity_id": str(uuid4()),
        "event_type": activity_type,
        "created_at": now,
        "details": {
            "note": note,
            "idempotency_key": idempotency_key,
            "metadata": metadata or {},
        },
    }
    _ACTIVITY_STORE[deal_id].append(activity_entry)
    record["version"] = int(record["version"]) + 1
    record["last_modified"] = now

    result = _normalize_response(
        success=True,
        operation="append_activity_log",
        deal_id=deal_id,
        record=record,
        timeline=[activity_entry],
        write_result={
            "status": "logged",
            "idempotency_key": idempotency_key,
            "activity_type": activity_type,
        },
        conflict_hints=_normalize_conflict_hints(record=record, expected_version=None),
    )
    _IDEMPOTENCY_CACHE[idempotency_cache_key] = deepcopy(result)
    return result


def update_crm(*, deal_id: str, note: str, message_id: str) -> Dict[str, Any]:
    """Backward-compatible helper used by execution paths.

    The existing workflow action `update_crm` is implemented as an activity log
    writeback, ensuring all mutations go through the normalized CRM tool layer.
    """
    return append_activity_log(
        deal_id=deal_id,
        activity_type="workflow_note",
        note=note,
        idempotency_key=f"message:{message_id}",
        metadata={"linked_message_id": message_id},
    )
