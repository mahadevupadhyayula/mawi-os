"""
Purpose:
Agent module `prompt_templates` for MAWI workflow decisioning/execution responsibilities.

Technical Details:
Implements typed agent logic that consumes context slices and produces deterministic, schema-aligned outputs for orchestration.
"""

from __future__ import annotations

import json
import random
from dataclasses import fields, is_dataclass
from pathlib import Path
import re
from string import Template
from threading import Lock
import time
from typing import Any, Mapping
from uuid import uuid4

from context.models import (
    CONTEXT_SCHEMA_VERSION,
    ActionPlanContext,
    DealContext,
    DecisionContext,
    ExecutionContext,
    InterventionDecisionContext,
    OutcomeContext,
    SignalContext,
)
from workflows.registry import (
    DEFAULT_WORKFLOW_NAME,
    get_generated_prompt_blocks,
    get_registered_workflow_names,
    get_workflow_release_version,
    is_known_workflow,
)
from data.repositories import PromptDiagnosticsRepository
from agents.prompt_blocks import PromptBlock, compose_template_from_blocks

PROMPT_DIR = Path(__file__).parent / "prompts"
COMMON_PROMPT_PROFILE = "common"
PROMPT_MANIFEST_PATH = PROMPT_DIR / "manifest.json"
REQUIRED_PROMPT_CONTRACT_KEYS = (
    "workflow_goal",
    "stage_name",
    "policy_mode",
)
PROMPT_SCHEMA_VERSION = "v1"
POLICY_INSTRUCTION_VERSION = "2026.04"
STRATEGY_INSTRUCTION_VERSION = "2026.04"
SCHEMA_COMPATIBILITY_MATRIX: dict[str, set[str]] = {
    "v1": {"v1"},
}
PROMPT_OUTPUT_MODELS: dict[str, type] = {
    "signal_prompt.txt": SignalContext,
    "context_prompt.txt": DealContext,
    "strategist_prompt.txt": DecisionContext,
    "intervention_prompt.txt": InterventionDecisionContext,
    "action_prompt.txt": ActionPlanContext,
    "execution_prompt.txt": ExecutionContext,
    "evaluator_prompt.txt": OutcomeContext,
}

PROMPT_REQUIRED_SECTIONS: dict[str, str] = {
    "role": "Role:",
    "task": "Task:",
    "constraints": "Constraints:",
    "output_fields": "Output Fields:",
    "safety_limits": "Safety Limits:",
    "tone_policy": "Tone Policy:",
    "legal_compliance_boundaries": "Legal/Compliance Boundaries:",
    "allowed_claims": "Allowed Claims:",
    "policy_validators": "Policy Validators:",
    "escalation_instructions": "Escalation Instructions:",
}

_PROMPT_FALLBACK_TELEMETRY: dict[str, int] = {}
_PROMPT_TELEMETRY_LOCK = Lock()
_TEMPLATE_TOKEN_PATTERN = re.compile(r"\$\{([_a-zA-Z][_a-zA-Z0-9]*)\}|\$([_a-zA-Z][_a-zA-Z0-9]*)")
_TRACE_SAMPLE_RATE = 0.2
_PROMPT_DIAGNOSTICS_REPO = PromptDiagnosticsRepository()


class PromptLintError(ValueError):
    """Raised when prompt templates fail lint or render-time contract checks."""


def _record_prompt_fallback_event(*, workflow_id: str, prompt_name: str, reason: str) -> None:
    key = f"{workflow_id}:{prompt_name}:{reason}"
    with _PROMPT_TELEMETRY_LOCK:
        _PROMPT_FALLBACK_TELEMETRY[key] = _PROMPT_FALLBACK_TELEMETRY.get(key, 0) + 1


def get_prompt_fallback_telemetry() -> dict[str, int]:
    with _PROMPT_TELEMETRY_LOCK:
        return dict(_PROMPT_FALLBACK_TELEMETRY)


def _validate_prompt_registry_manifest(manifest: Mapping[str, Any]) -> None:
    registry = manifest.get("prompt_registry_index")
    if not isinstance(registry, list) or not registry:
        raise ValueError("Prompt manifest must include a non-empty prompt_registry_index list.")

    for entry in registry:
        prompt_id = str(entry.get("prompt_id", ""))
        if not prompt_id:
            raise ValueError("Prompt registry entries must include prompt_id.")
        status = str(entry.get("status", ""))
        if status not in {"draft", "active", "deprecated"}:
            raise ValueError(f"Prompt registry entry '{prompt_id}' has invalid status.")
        if not str(entry.get("owner", "")):
            raise ValueError(f"Prompt registry entry '{prompt_id}' must include an owner.")
        if not str(entry.get("version", "")):
            raise ValueError(f"Prompt registry entry '{prompt_id}' must include a version.")

        changelog = entry.get("changelog")
        if not isinstance(changelog, list) or not changelog:
            raise ValueError(f"Prompt registry entry '{prompt_id}' must include changelog entries.")

        workflow_id = str(entry.get("workflow_id", ""))
        release_version = str(entry.get("workflow_release_version", ""))
        is_planned_workflow = bool(entry.get("planned_workflow", False))

        if workflow_id and is_known_workflow(workflow_id):
            expected_release = get_workflow_release_version(workflow_id)
            if release_version != expected_release:
                raise ValueError(
                    f"Prompt registry entry '{prompt_id}' release mismatch: "
                    f"expected workflow release version '{expected_release}', got '{release_version}'."
                )
            continue

        if workflow_id and not is_planned_workflow:
            raise ValueError(
                f"Prompt registry entry '{prompt_id}' references unknown workflow_id '{workflow_id}'. "
                "Set planned_workflow=true only for planned registrations."
            )

        if is_planned_workflow and status != "draft":
            raise ValueError(
                f"Prompt registry entry '{prompt_id}' references planned workflow '{workflow_id}' "
                f"and must use status 'draft', got '{status}'."
            )


def load_prompt_manifest() -> dict[str, Any]:
    manifest = json.loads(PROMPT_MANIFEST_PATH.read_text(encoding="utf-8"))
    _validate_prompt_registry_manifest(manifest)
    return manifest


def _compose_generated_workflow_prompt(name: str, workflow_id: str) -> str | None:
    generated_blocks = get_generated_prompt_blocks(workflow_id)
    if not generated_blocks:
        return None
    role = name.replace("_prompt.txt", "")
    blocks = tuple(
        PromptBlock(block_type=str(item.get("block_type", "")), content=str(item.get("content", "")))
        for item in generated_blocks
    )
    return compose_template_from_blocks(role=role, blocks=blocks)


def _resolve_prompt_path(name: str, workflow_id: str) -> tuple[Path | None, str, bool, str | None]:
    workflow_prompt_path = PROMPT_DIR / workflow_id / name
    if workflow_prompt_path.exists():
        return workflow_prompt_path, workflow_id, False, None

    generated_prompt = _compose_generated_workflow_prompt(name, workflow_id)
    if generated_prompt is not None:
        _record_prompt_fallback_event(workflow_id=workflow_id, prompt_name=name, reason="generated_workflow_prompt")
        _PROMPT_DIAGNOSTICS_REPO.increment_counter(metric_name="fallback_events")
        return None, workflow_id, False, generated_prompt

    common_prompt_path = PROMPT_DIR / COMMON_PROMPT_PROFILE / name
    if common_prompt_path.exists():
        _record_prompt_fallback_event(workflow_id=workflow_id, prompt_name=name, reason="missing_workflow_prompt")
        _PROMPT_DIAGNOSTICS_REPO.increment_counter(metric_name="fallback_events")
        return common_prompt_path, COMMON_PROMPT_PROFILE, True, None

    raise FileNotFoundError(
        f"Unable to resolve prompt template '{name}' for workflow '{workflow_id}'. "
        f"Checked '{workflow_prompt_path}' then '{common_prompt_path}'."
    )


def load_prompt(name: str, workflow_id: str) -> str:
    path, _, _, generated_prompt = _resolve_prompt_path(name, workflow_id)
    if generated_prompt is not None:
        return generated_prompt
    assert path is not None
    return path.read_text(encoding="utf-8")


def _resolve_profile_version(profile_id: str) -> str:
    manifest = load_prompt_manifest()
    profiles = manifest.get("profiles", {})
    profile = profiles.get(profile_id, {})
    return str(profile.get("version", manifest.get("manifest_version", "unknown")))


def _sanitize_trace_text(text: str) -> str:
    scrubbed = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", "<redacted_email>", text)
    scrubbed = re.sub(r"\b\d{8,}\b", "<redacted_id>", scrubbed)
    return scrubbed


def _required_json_fields(output_model: type) -> list[str]:
    if not is_dataclass(output_model):
        raise TypeError(f"output_model must be a dataclass type, got: {output_model!r}")
    return [field.name for field in fields(output_model) if field.name != "meta"]


def required_json_fields(output_model: type) -> list[str]:
    """Public helper for resolving required payload fields from an output dataclass."""
    return _required_json_fields(output_model)


def validate_model_output_json(
    *,
    model_output: str,
    required_json_fields: list[str],
    stage_name: str,
) -> dict[str, Any]:
    """Parse and validate model output JSON for orchestrator/audit consumers."""
    errors: list[dict[str, Any]] = []
    payload: Any = None
    try:
        payload = json.loads(model_output)
    except json.JSONDecodeError as exc:
        errors.append(
            {
                "code": "invalid_json",
                "stage_name": stage_name,
                "message": "Model output is not valid JSON.",
                "details": {"error": str(exc)},
            }
        )
        return {"ok": False, "payload": None, "errors": errors}

    if not isinstance(payload, dict):
        errors.append(
            {
                "code": "invalid_payload_type",
                "stage_name": stage_name,
                "message": "Model output JSON must decode to an object.",
                "details": {"parsed_type": type(payload).__name__},
            }
        )
        return {"ok": False, "payload": None, "errors": errors}

    missing_fields = [field for field in required_json_fields if field not in payload]
    if missing_fields:
        errors.append(
            {
                "code": "missing_required_fields",
                "stage_name": stage_name,
                "message": "Model output is missing required fields.",
                "details": {"missing_fields": missing_fields},
            }
        )

    confidence = payload.get("confidence")
    if not isinstance(confidence, (int, float)):
        errors.append(
            {
                "code": "invalid_confidence_type",
                "stage_name": stage_name,
                "message": "confidence must be numeric.",
                "details": {"value": confidence},
            }
        )
    elif not 0.0 <= float(confidence) <= 1.0:
        errors.append(
            {
                "code": "invalid_confidence_range",
                "stage_name": stage_name,
                "message": "confidence must be within [0, 1].",
                "details": {"value": confidence},
            }
        )

    return {"ok": not errors, "payload": payload if not errors else None, "errors": errors}


def _extract_prompt_schema_version(template_text: str, name: str) -> str:
    match = re.search(r"^schema_version:\s*(\S+)\s*$", template_text, flags=re.MULTILINE)
    if not match:
        raise ValueError(f"Prompt template '{name}' must declare a schema version (schema_version: vN).")
    return match.group(1)


def _resolve_output_model(name: str, contract: Mapping[str, Any]) -> type:
    output_model = contract.get("output_model") or PROMPT_OUTPUT_MODELS.get(name)
    if output_model is None:
        raise ValueError(f"Unable to resolve output model for prompt '{name}'.")
    return output_model


def _normalize_contract(name: str, prompt_contract: Mapping[str, Any] | None) -> dict[str, str]:
    contract = dict(prompt_contract or {})
    contract.setdefault("workflow_id", DEFAULT_WORKFLOW_NAME)
    workflow_id = str(contract["workflow_id"])
    if not is_known_workflow(workflow_id):
        known_workflows = ", ".join(sorted(load_prompt_manifest().get("profiles", {}).keys()))
        raise ValueError(
            f"Unknown workflow_id '{workflow_id}' in prompt contract. Supported prompt profiles: {known_workflows}"
        )

    missing = [key for key in REQUIRED_PROMPT_CONTRACT_KEYS if not contract.get(key)]
    if missing:
        missing_csv = ", ".join(sorted(missing))
        raise ValueError(f"prompt contract missing required keys: {missing_csv}")

    output_model = _resolve_output_model(name, contract)
    required_fields = _required_json_fields(output_model)

    normalized: dict[str, str] = {}
    for key, value in contract.items():
        normalized[key] = str(value)
    normalized["prompt_schema_version"] = PROMPT_SCHEMA_VERSION
    normalized["policy_instruction_version"] = str(
        contract.get("policy_instruction_version", POLICY_INSTRUCTION_VERSION)
    )
    normalized["strategy_instruction_version"] = str(
        contract.get("strategy_instruction_version", STRATEGY_INSTRUCTION_VERSION)
    )
    normalized["context_schema_version"] = CONTEXT_SCHEMA_VERSION
    normalized["output_model"] = output_model.__name__
    normalized["required_json_fields"] = json.dumps(required_fields)
    normalized["required_json_fields_csv"] = ", ".join(required_fields)
    return normalized


def _contract_header(contract: Mapping[str, str]) -> str:
    return "\n".join(
        [
            "PROMPT_CONTRACT",
            f"workflow_id: {contract['workflow_id']}",
            f"workflow_goal: {contract['workflow_goal']}",
            f"stage_name: {contract['stage_name']}",
            f"policy_mode: {contract['policy_mode']}",
            f"prompt_schema_version: {contract['prompt_schema_version']}",
            f"policy_instruction_version: {contract['policy_instruction_version']}",
            f"strategy_instruction_version: {contract['strategy_instruction_version']}",
            f"context_schema_version: {contract['context_schema_version']}",
            f"output_model: {contract['output_model']}",
            f"required_json_fields: {contract['required_json_fields']}",
        ]
    )


def _extract_template_placeholders(template_text: str) -> set[str]:
    names: set[str] = set()
    for match in _TEMPLATE_TOKEN_PATTERN.finditer(template_text):
        names.add(match.group(1) or match.group(2) or "")
    names.discard("")
    return names


def _ensure_required_sections(template_text: str, template_name: str) -> list[str]:
    missing_sections = []
    for section, marker in PROMPT_REQUIRED_SECTIONS.items():
        if marker not in template_text:
            missing_sections.append(section)
    errors = []
    if missing_sections:
        errors.append(
            f"missing required sections: {', '.join(missing_sections)}"
        )
    return errors


def _style_ambiguity_checks(template_text: str) -> list[str]:
    errors: list[str] = []
    constraints_line = next((line for line in template_text.splitlines() if line.startswith("Constraints:")), "")
    safety_line = next((line for line in template_text.splitlines() if line.startswith("Safety Limits:")), "")
    combined = " ".join((constraints_line, safety_line)).lower()
    if "always" in combined and "never" in combined:
        errors.append("conflicting constraints detected (contains both 'always' and 'never').")
    confidence_patterns = [
        r"confidence\s*(in|between)?\s*\[\s*0\s*,\s*1\s*\]",
        r"confidence\s*between\s*0\s*and\s*1",
    ]
    if not any(re.search(pattern, combined) for pattern in confidence_patterns):
        errors.append("missing confidence bounds (must constrain confidence to [0,1]).")
    return errors


def lint_prompt_template(
    *,
    template_name: str,
    workflow_id: str,
    template_text: str,
    render_variables: Mapping[str, str],
    extra_render_keys: set[str] | None = None,
) -> list[str]:
    errors: list[str] = []
    errors.extend(_ensure_required_sections(template_text, template_name))
    errors.extend(_style_ambiguity_checks(template_text))

    placeholders = _extract_template_placeholders(template_text)
    missing_placeholders = sorted(placeholders - set(render_variables.keys()))
    if missing_placeholders:
        errors.append(f"unresolved placeholders: {', '.join(missing_placeholders)}")

    unused_render_vars = sorted((extra_render_keys or set()) - placeholders)
    if unused_render_vars:
        errors.append(f"unused render kwargs: {', '.join(unused_render_vars)}")

    return [f"[{workflow_id}/{template_name}] {error}" for error in errors]


def generate_prompt_health_report() -> dict[str, Any]:
    report_rows: list[dict[str, Any]] = []
    for workflow_id in get_registered_workflow_names():
        for template_name in sorted(PROMPT_OUTPUT_MODELS.keys()):
            contract = _normalize_contract(
                template_name,
                {
                    "workflow_id": workflow_id,
                    "workflow_goal": "Prompt health lint run.",
                    "stage_name": template_name.replace("_prompt.txt", ""),
                    "policy_mode": "observe_only",
                },
            )
            template_text = load_prompt(template_name, workflow_id)
            lint_errors = lint_prompt_template(
                template_name=template_name,
                workflow_id=workflow_id,
                template_text=template_text,
                render_variables=contract,
            )
            report_rows.append(
                {
                    "workflow_id": workflow_id,
                    "agent_prompt": template_name,
                    "status": "pass" if not lint_errors else "fail",
                    "errors": lint_errors,
                }
            )
    failures = [row for row in report_rows if row["status"] == "fail"]
    return {
        "summary": {
            "total": len(report_rows),
            "passed": len(report_rows) - len(failures),
            "failed": len(failures),
        },
        "rows": report_rows,
    }


def validate_prompt_health_report(report: Mapping[str, Any]) -> None:
    failing = [row for row in report.get("rows", []) if row.get("status") != "pass"]
    if failing:
        details = "; ".join(
            f"{row.get('workflow_id')}/{row.get('agent_prompt')}: {', '.join(row.get('errors', []))}"
            for row in failing
        )
        raise PromptLintError(f"Prompt health report contains failures: {details}")


def render_prompt(name: str, *, prompt_contract: Mapping[str, Any] | None = None, **kwargs: str) -> str:
    started = time.perf_counter()
    run_id = str((prompt_contract or {}).get("run_id") or uuid4())
    workflow_id = str((prompt_contract or {}).get("workflow_id") or DEFAULT_WORKFLOW_NAME)
    agent_id = str((prompt_contract or {}).get("agent_id") or (prompt_contract or {}).get("stage_name") or "unknown_agent")
    profile_id = workflow_id
    profile_version = _resolve_profile_version(profile_id)
    fallback_used = False
    try:
        contract = _normalize_contract(name, prompt_contract)
        workflow_id = contract["workflow_id"]
        agent_id = str(contract.get("agent_id") or contract.get("stage_name") or agent_id)
        _PROMPT_DIAGNOSTICS_REPO.assign_variant(run_id=run_id, workflow_id=workflow_id)
        prompt_path, resolved_profile_id, fallback_used, generated_prompt = _resolve_prompt_path(name, contract["workflow_id"])
        profile_id = resolved_profile_id
        profile_version = _resolve_profile_version(profile_id)
        prompt_text = generated_prompt if generated_prompt is not None else prompt_path.read_text(encoding="utf-8")
        declared_schema = _extract_prompt_schema_version(prompt_text, name)
        compatible_context_versions = SCHEMA_COMPATIBILITY_MATRIX.get(declared_schema, set())
        if CONTEXT_SCHEMA_VERSION not in compatible_context_versions:
            _PROMPT_DIAGNOSTICS_REPO.increment_counter(metric_name="schema_validation_errors")
            raise ValueError(
                f"Prompt schema '{declared_schema}' is not compatible with context schema '{CONTEXT_SCHEMA_VERSION}'."
            )

        render_variables = {**contract, **kwargs}
        lint_errors = lint_prompt_template(
            template_name=name,
            workflow_id=contract["workflow_id"],
            template_text=prompt_text,
            render_variables=render_variables,
            extra_render_keys=set(kwargs.keys()),
        )
        if lint_errors:
            _PROMPT_DIAGNOSTICS_REPO.increment_counter(metric_name="schema_validation_errors")
            raise PromptLintError("; ".join(lint_errors))

        template = Template(prompt_text)
        rendered_body = template.substitute(**render_variables)
        rendered = f"{_contract_header(contract)}\n\n{rendered_body}"
        latency_ms = int((time.perf_counter() - started) * 1000)
        sampled = random.random() < _TRACE_SAMPLE_RATE
        trace_payload = (
            {
                "contract": contract,
                "render_kwargs": {key: str(value) for key, value in kwargs.items()},
                "rendered_prompt": _sanitize_trace_text(rendered),
            }
            if sampled
            else None
        )
        _PROMPT_DIAGNOSTICS_REPO.log_render_event(
            run_id=run_id,
            workflow_id=contract["workflow_id"],
            agent_id=agent_id,
            prompt_name=name,
            prompt_profile_id=profile_id,
            prompt_profile_version=profile_version,
            prompt_schema_version=declared_schema,
            latency_ms=latency_ms,
            status="success",
            fallback_used=fallback_used,
            confidence=float(kwargs["confidence"]) if "confidence" in kwargs else None,
            trace_sampled=sampled,
            trace_payload=trace_payload,
        )
        return rendered
    except KeyError:
        _PROMPT_DIAGNOSTICS_REPO.increment_counter(metric_name="parse_failures")
        raise
    except Exception as exc:
        latency_ms = int((time.perf_counter() - started) * 1000)
        _PROMPT_DIAGNOSTICS_REPO.log_render_event(
            run_id=run_id,
            workflow_id=workflow_id,
            agent_id=agent_id,
            prompt_name=name,
            prompt_profile_id=profile_id,
            prompt_profile_version=profile_version,
            prompt_schema_version=PROMPT_SCHEMA_VERSION,
            latency_ms=latency_ms,
            status="error",
            fallback_used=fallback_used,
            error_type=exc.__class__.__name__,
            trace_sampled=False,
        )
        raise


def get_prompt_diagnostics_report(*, limit: int = 25) -> dict[str, Any]:
    return _PROMPT_DIAGNOSTICS_REPO.diagnostics_report(limit=limit)


def attach_prompt_outcome(*, run_id: str, outcome_label: str) -> None:
    _PROMPT_DIAGNOSTICS_REPO.attach_outcome_label(run_id=run_id, outcome_label=outcome_label)


def attach_prompt_outcome_metrics(
    *,
    run_id: str,
    reply_received: bool,
    meeting_booked: bool,
    execution_success: bool,
) -> None:
    _PROMPT_DIAGNOSTICS_REPO.record_outcome_metrics(
        run_id=run_id,
        reply_received=reply_received,
        meeting_booked=meeting_booked,
        execution_success=execution_success,
    )


def attach_prompt_rejection(*, action_id: str) -> None:
    _PROMPT_DIAGNOSTICS_REPO.record_rejection(action_id=action_id)


def attach_prompt_run_metadata(
    *,
    run_id: str,
    agent_id: str,
    prompt_name: str,
    llm_enabled: bool | None = None,
    provider: str | None = None,
    model: str | None = None,
    llm_latency_ms: int | None = None,
    token_usage: dict[str, int] | None = None,
    fallback_reason: str | None = None,
) -> None:
    _PROMPT_DIAGNOSTICS_REPO.attach_run_metadata(
        run_id=run_id,
        agent_id=agent_id,
        prompt_name=prompt_name,
        llm_enabled=llm_enabled,
        provider=provider,
        model=model,
        llm_latency_ms=llm_latency_ms,
        token_usage=token_usage,
        fallback_reason=fallback_reason,
    )
