import unittest

from agents.execution_agent import execution_agent
from context.models import ActionPlanContext, ActionStep
from approval.policy import max_risk_tier_for_workflow_phase


class TestPolicyControls(unittest.TestCase):
    def test_workflow_phase_risk_tier_defaults(self) -> None:
        self.assertEqual(max_risk_tier_for_workflow_phase("deal_followup_workflow", "autonomous"), "medium")
        self.assertEqual(max_risk_tier_for_workflow_phase("new_deal_outreach_workflow", "autonomous"), "low")

    def test_pre_execution_policy_validator_blocks_prohibited_claims(self) -> None:
        plan = ActionPlanContext(reasoning="seed", confidence=0.9, status="approved", plan_id="plan-1")
        plan.steps = [
            ActionStep(
                step_id="s1",
                order=1,
                channel="email",
                action_type="send_email",
                subject="Guaranteed results",
                body_draft="We guarantee a 100% response rate.",
                status="approved",
            )
        ]

        execution = execution_agent(plan, deal_id="d1", contact_name="Taylor", workflow_id="deal_followup_workflow")

        self.assertEqual(execution.status, "failed")
        self.assertEqual(plan.steps[0].last_error, "generated_output_policy_violation")
        event_types = [event.get("event_type") for event in execution.tool_events if "event_type" in event]
        self.assertIn("blocked_by_output_policy", event_types)


if __name__ == "__main__":
    unittest.main()
