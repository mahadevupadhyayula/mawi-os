import unittest

from agents.action_agent import action_agent
from agents.strategist_agent import strategist_agent
from context.models import DealContext, DecisionContext, SignalContext


class TestMemoryAdaptation(unittest.TestCase):
    def _signal(self) -> SignalContext:
        return SignalContext(reasoning="seed", confidence=0.8, urgency="high")

    def _deal(self) -> DealContext:
        return DealContext(
            reasoning="seed",
            confidence=0.8,
            persona="vp_sales",
            deal_stage="proposal",
            known_objections=["budget timing"],
        )

    def test_strategist_without_memory_uses_baseline_and_default_confidence(self) -> None:
        decision = strategist_agent(self._signal(), self._deal(), memory_evidence=[])

        self.assertEqual(decision.strategy_type, "roi_framing")
        self.assertEqual(decision.memory_evidence_used, [])
        self.assertEqual(decision.memory_confidence_impact, 0.0)
        self.assertEqual(decision.confidence, 0.78)
        self.assertIn("No memory evidence available", decision.memory_rationale)

    def test_strategist_with_memory_biases_strategy_and_confidence(self) -> None:
        memory = [
            {"snippet": "ROI proof increased replies", "confidence_impact": 0.06},
            {"snippet": "ROI subject line converted", "confidence_impact": 0.05},
        ]

        decision = strategist_agent(self._signal(), self._deal(), memory_evidence=memory)

        self.assertEqual(decision.strategy_type, "roi_framing")
        self.assertEqual(decision.memory_evidence_used, memory)
        self.assertEqual(decision.memory_confidence_impact, 0.11)
        self.assertEqual(decision.confidence, 0.89)
        self.assertIn("Used 2 memory evidence item(s)", decision.memory_rationale)

    def test_action_agent_without_memory_preserves_default_copy(self) -> None:
        decision = DecisionContext(
            reasoning="seed",
            confidence=0.78,
            strategy_id="strat-roi_framing",
            strategy_type="roi_framing",
            message_goal="restart_conversation",
            fallback_strategy="social_proof",
            memory_evidence_used=[],
            memory_confidence_impact=0.0,
            memory_rationale="No memory evidence available; used baseline strategist rules.",
        )

        action_plan = action_agent(decision, self._deal())
        email_step = action_plan.steps[0]

        self.assertEqual(email_step.subject, "Quick follow-up on your rollout goals")
        self.assertIn("2-point plan and timeline options", email_step.body_draft)

    def test_action_agent_with_memory_uses_adaptive_copy_and_cta(self) -> None:
        decision = DecisionContext(
            reasoning="seed",
            confidence=0.9,
            strategy_id="strat-roi_framing",
            strategy_type="roi_framing",
            message_goal="restart_conversation",
            fallback_strategy="social_proof",
            memory_evidence_used=[{"snippet": "ROI messaging performed best", "confidence_impact": 0.1}],
            memory_confidence_impact=0.1,
            memory_rationale="Used memory evidence.",
        )

        action_plan = action_agent(decision, self._deal())
        email_step = action_plan.steps[0]

        self.assertEqual(email_step.subject, "Follow-up: ROI path based on similar deals")
        self.assertIn("hold a 15-minute slot this week", email_step.body_draft)


if __name__ == "__main__":
    unittest.main()
