import unittest

from agents.action_agent import action_agent
from agents.execution_agent import execution_agent
from context.models import ActionStep, DealContext, DecisionContext


class TestActionPlanExecution(unittest.TestCase):
    def _deal(self) -> DealContext:
        return DealContext(reasoning="seed", confidence=0.8, persona="vp_sales", deal_stage="proposal")

    def test_action_agent_generates_multistep_plan(self) -> None:
        decision = DecisionContext(
            reasoning="seed",
            confidence=0.8,
            strategy_id="strat-risk",
            strategy_type="risk_reversal",
            message_goal="restart_conversation",
            fallback_strategy="social_proof",
        )

        plan = action_agent(decision, self._deal())

        self.assertGreaterEqual(len(plan.steps), 2)
        self.assertEqual([step.order for step in plan.steps], [1, 2])

    def test_execution_agent_skips_previously_executed_step(self) -> None:
        step_1 = ActionStep(
            step_id="step-1",
            order=1,
            channel="email",
            action_type="send_email",
            subject="hello",
            body_draft="body",
            status="executed",
            retry_count=1,
            execution_result={"success": True, "message_id": "m-1"},
        )
        step_2 = ActionStep(
            step_id="step-2",
            order=2,
            channel="crm",
            action_type="update_crm",
            body_draft="note",
            status="approved",
        )

        decision = DecisionContext(
            reasoning="seed",
            confidence=0.8,
            strategy_id="strat-risk",
            strategy_type="risk_reversal",
            message_goal="restart_conversation",
            fallback_strategy="social_proof",
        )
        plan = action_agent(decision, self._deal())
        plan.steps = [step_1, step_2]
        plan.status = "approved"

        execution = execution_agent(plan, deal_id="deal-1", contact_name="Taylor")

        self.assertEqual(execution.status, "executed")
        self.assertEqual(step_1.retry_count, 1)
        self.assertEqual(step_1.status, "executed")
        self.assertGreaterEqual(step_2.retry_count, 1)
        self.assertEqual(step_2.status, "executed")

    def test_execution_agent_dispatches_sms_channel(self) -> None:
        step_1 = ActionStep(
            step_id="step-sms",
            order=1,
            channel="sms",
            action_type="send_sms",
            body_draft="Quick check-in from MAWI.",
            status="approved",
        )
        decision = DecisionContext(
            reasoning="seed",
            confidence=0.8,
            strategy_id="strat-risk",
            strategy_type="risk_reversal",
            message_goal="restart_conversation",
            fallback_strategy="social_proof",
        )
        plan = action_agent(decision, self._deal())
        plan.steps = [step_1]
        plan.status = "approved"

        execution = execution_agent(plan, deal_id="deal-1", contact_name="Taylor")

        self.assertEqual(execution.status, "executed")
        self.assertEqual(step_1.status, "executed")
        self.assertTrue(step_1.execution_result.get("success"))
        self.assertIn("sms_id", step_1.execution_result)

    def test_execution_agent_blocks_channel_not_in_allow_list(self) -> None:
        step_1 = ActionStep(
            step_id="step-sms",
            order=1,
            channel="sms",
            action_type="send_sms",
            body_draft="Quick check-in from MAWI.",
            status="approved",
        )
        decision = DecisionContext(
            reasoning="seed",
            confidence=0.8,
            strategy_id="strat-risk",
            strategy_type="risk_reversal",
            message_goal="restart_conversation",
            fallback_strategy="social_proof",
        )
        plan = action_agent(decision, self._deal())
        plan.steps = [step_1]
        plan.status = "approved"

        execution = execution_agent(
            plan,
            deal_id="deal-1",
            contact_name="Taylor",
            allowed_channels=("email", "crm"),
            max_risk_tier="high",
        )

        self.assertEqual(execution.status, "failed")
        self.assertEqual(step_1.status, "failed")
        self.assertEqual(step_1.last_error, "channel_not_allowed")


if __name__ == "__main__":
    unittest.main()
