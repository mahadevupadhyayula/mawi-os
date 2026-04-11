"""
Purpose:
Implements the Strategist Agent that converts signal and deal context into a recommended strategy for next-best action.

Technical Details:
Renders strategist prompt templates, applies deterministic strategy selection logic for MVP behavior, and returns typed DecisionContext payloads via shared contracts.
"""

from __future__ import annotations

from agents.contracts import make_result
from agents.prompt_templates import render_prompt
from context.models import DealContext, DecisionContext, SignalContext


def strategist_agent(
    signal_context: SignalContext,
    deal_context: DealContext,
    memory_evidence: list[dict] | None = None,
    *,
    workflow_id: str = "deal_followup_workflow",
    run_id: str | None = None,
) -> DecisionContext:
    _ = render_prompt(
        "strategist_prompt.txt",
        prompt_contract={
            "workflow_goal": "Select a next-best strategy that restarts stalled conversations.",
            "stage_name": "strategist_agent",
            "policy_mode": "policy_guided",
            "output_model": DecisionContext,
            "workflow_id": workflow_id,
            "run_id": run_id or "adhoc-run",
            "agent_id": "strategist_agent",
        },
    )
    baseline_strategy = "roi_framing" if "budget timing" in deal_context.known_objections else "risk_reduction"
    evidence = [item for item in (memory_evidence or []) if isinstance(item, dict)]
    evidence_text = " ".join(item.get("snippet", "").lower() for item in evidence)

    raw_impact = round(sum(float(item.get("confidence_impact", 0.0)) for item in evidence), 3)
    # Guardrail: preserve the current no-memory confidence band while allowing bounded lift with evidence.
    memory_confidence_impact = max(0.0, min(raw_impact, 0.15))

    if not evidence:
        strategy_type = baseline_strategy
        confidence = 0.78
        memory_rationale = "No memory evidence available; used baseline strategist rules."
        reasoning = f"Selected {strategy_type} based on objections and urgency={signal_context.urgency}."
    else:
        if "roi" in evidence_text:
            strategy_type = "roi_framing"
        elif "risk" in evidence_text:
            strategy_type = "risk_reduction"
        else:
            strategy_type = baseline_strategy
        confidence = 0.78 + memory_confidence_impact
        memory_rationale = (
            f"Used {len(evidence)} memory evidence item(s) to bias deterministic strategy selection "
            f"and apply confidence impact +{memory_confidence_impact:.3f}."
        )
        reasoning = f"Selected {strategy_type} based on objections and urgency={signal_context.urgency}. {memory_rationale}"
    result = make_result(
        DecisionContext(
            strategy_id=f"strat-{strategy_type}",
            strategy_type=strategy_type,
            message_goal="restart_conversation",
            fallback_strategy="social_proof",
            memory_evidence_used=evidence,
            memory_confidence_impact=memory_confidence_impact,
            memory_rationale=memory_rationale,
            reasoning=reasoning,
            confidence=confidence,
        ),
        reasoning,
        confidence,
    )
    return result.payload
