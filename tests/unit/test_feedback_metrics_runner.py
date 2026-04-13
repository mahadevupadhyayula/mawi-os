from context.models import ContextEnvelope, MetaContext
from orchestrator.runner import WorkflowOrchestrator


def test_feedback_stage_parsing_defaults_and_bounds() -> None:
    orchestrator = WorkflowOrchestrator()
    envelope = ContextEnvelope(meta=MetaContext(deal_id="deal-1"), raw_data={})
    assert orchestrator._feedback_stage(envelope) == 1

    envelope.raw_data["memory_feedback_stage"] = "3"
    assert orchestrator._feedback_stage(envelope) == 3

    envelope.raw_data["memory_feedback_stage"] = 999
    assert orchestrator._feedback_stage(envelope) == 3


def test_feedback_metrics_include_quality_block_counter() -> None:
    orchestrator = WorkflowOrchestrator()
    metrics = orchestrator.feedback_metrics.snapshot()
    assert "adaptation_blocked_quality" in metrics
    assert metrics["adaptation_blocked_quality"] == 0
