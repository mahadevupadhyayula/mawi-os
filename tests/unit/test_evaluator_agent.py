from agents.contracts import ExecutionOutcome
from agents.evaluator_agent import evaluator_agent
from context.models import ExecutionContext, OutcomeContext


def _execution(status: str) -> ExecutionContext:
    return ExecutionContext(
        execution_id="exec-1",
        status=status,
        reasoning="seed",
        confidence=0.8,
    )


def test_evaluator_negative_when_execution_not_successful() -> None:
    result = evaluator_agent(_execution("failed"), ExecutionOutcome(reply_received=False, meeting_booked=False))

    assert isinstance(result, OutcomeContext)
    assert result.outcome_label == "negative"
    assert "retry" in result.recommended_adjustment.lower()


def test_evaluator_positive_when_executed_and_reply_received() -> None:
    result = evaluator_agent(_execution("executed"), ExecutionOutcome(reply_received=True, meeting_booked=False))

    assert result.outcome_label == "positive"
    assert "ROI" in result.insight


def test_evaluator_neutral_when_executed_without_reply() -> None:
    result = evaluator_agent(_execution("executed"), ExecutionOutcome(reply_received=False, meeting_booked=False))

    assert result.outcome_label == "neutral"
    assert result.confidence == 0.65


def test_evaluator_delayed_positive_when_interested_note_present() -> None:
    result = evaluator_agent(
        _execution("executed"),
        ExecutionOutcome(reply_received=False, meeting_booked=False, notes="Prospect interested; asks to reconnect next quarter."),
    )

    assert result.outcome_label == "positive"
    assert "Late interest signal" in result.insight
