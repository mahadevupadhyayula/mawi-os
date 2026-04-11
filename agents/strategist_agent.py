from __future__ import annotations

from agents.contracts import make_result
from agents.prompt_templates import render_prompt
from context.models import DealContext, DecisionContext, SignalContext


def strategist_agent(signal_context: SignalContext, deal_context: DealContext) -> DecisionContext:
    _ = render_prompt("strategist_prompt.txt")
    strategy_type = "roi_framing" if "budget timing" in deal_context.known_objections else "risk_reduction"
    reasoning = f"Selected {strategy_type} based on objections and urgency={signal_context.urgency}."
    confidence = 0.78
    result = make_result(
        DecisionContext(
            strategy_id=f"strat-{strategy_type}",
            strategy_type=strategy_type,
            message_goal="restart_conversation",
            fallback_strategy="social_proof",
            reasoning=reasoning,
            confidence=confidence,
        ),
        reasoning,
        confidence,
    )
    return result.payload
