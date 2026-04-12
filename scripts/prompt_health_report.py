#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Mapping

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from agents.prompt_templates import (
    generate_prompt_health_report,
    get_prompt_diagnostics_report,
    validate_prompt_health_report,
)


PROMOTION_GATE_THRESHOLDS = {
    "min_agent_runs_for_rate_checks": 5,
    "min_outcome_samples_for_lift": 5,
    "max_parse_failure_rate": 0.05,
    "max_policy_violation_rate": 0.05,
    "max_approval_rejection_rate": 0.35,
    "min_downstream_lift": -0.05,
}


def validate_promotion_thresholds(report: Mapping[str, Any], *, thresholds: Mapping[str, float | int]) -> None:
    rollouts = report.get("experiments", {}).get("rollouts", [])
    promotion_stages = {"canary", "full"}
    should_enforce = any(
        str(row.get("rollout_phase", "")) in promotion_stages and bool(str(row.get("active_release_id", "")).strip())
        for row in rollouts
    )
    if not should_enforce:
        return

    failures: list[str] = []
    agent_metrics = report.get("performance", {}).get("agent_metrics", [])
    for agent in agent_metrics:
        agent_id = str(agent.get("agent_id", "unknown"))
        total_runs = int(agent.get("total_runs", 0) or 0)
        if total_runs >= int(thresholds["min_agent_runs_for_rate_checks"]):
            parse_failure_rate = float(agent.get("parse_failure_rate", 0.0) or 0.0)
            if parse_failure_rate > float(thresholds["max_parse_failure_rate"]):
                failures.append(
                    f"{agent_id} parse_failure_rate={parse_failure_rate:.3f} exceeds "
                    f"max={float(thresholds['max_parse_failure_rate']):.3f}"
                )
            policy_violation_rate = float(agent.get("policy_violation_rate", 0.0) or 0.0)
            if policy_violation_rate > float(thresholds["max_policy_violation_rate"]):
                failures.append(
                    f"{agent_id} policy_violation_rate={policy_violation_rate:.3f} exceeds "
                    f"max={float(thresholds['max_policy_violation_rate']):.3f}"
                )

        for stage in agent.get("approval_rejection_rate_by_stage", []):
            total_actions = int(stage.get("total_actions", 0) or 0)
            if total_actions >= int(thresholds["min_agent_runs_for_rate_checks"]):
                rejection_rate = float(stage.get("rejection_rate", 0.0) or 0.0)
                if rejection_rate > float(thresholds["max_approval_rejection_rate"]):
                    failures.append(
                        f"{agent_id}/{stage.get('stage')} approval_rejection_rate={rejection_rate:.3f} exceeds "
                        f"max={float(thresholds['max_approval_rejection_rate']):.3f}"
                    )

        lift = agent.get("downstream_outcome_lift_correlation", {})
        outcome_samples = int(lift.get("outcome_samples", 0) or 0)
        if outcome_samples >= int(thresholds["min_outcome_samples_for_lift"]):
            lift_value = float(lift.get("lift", 0.0) or 0.0)
            if lift_value < float(thresholds["min_downstream_lift"]):
                failures.append(
                    f"{agent_id} downstream_lift={lift_value:.3f} below min={float(thresholds['min_downstream_lift']):.3f}"
                )

    if failures:
        raise RuntimeError("Promotion gate thresholds failed: " + "; ".join(failures))


def main() -> int:
    lint_report = generate_prompt_health_report()
    diagnostics_report = get_prompt_diagnostics_report(limit=100)
    report = {
        "lint": lint_report,
        "diagnostics": diagnostics_report,
        "promotion_gate": {
            "thresholds": PROMOTION_GATE_THRESHOLDS,
        },
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    validate_prompt_health_report(lint_report)
    validate_promotion_thresholds(diagnostics_report, thresholds=PROMOTION_GATE_THRESHOLDS)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
