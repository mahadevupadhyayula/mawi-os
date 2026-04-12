from context.models import SignalContext
from agents.signal_agent import signal_agent


def test_signal_agent_missing_days_defaults_to_not_stalled() -> None:
    result = signal_agent({})

    assert isinstance(result, SignalContext)
    assert result.days_since_reply == 0
    assert result.stalled is False
    assert result.urgency == "low"
    assert result.trigger_reason == "not_stalled"
    assert result.reasoning == "Deal has no reply for 0 days."
    assert result.confidence == 0.7


def test_signal_agent_days_since_reply_boundary_values() -> None:
    before_threshold = signal_agent({"days_since_reply": 4})
    at_stalled_threshold = signal_agent({"days_since_reply": 5})
    at_high_urgency_threshold = signal_agent({"days_since_reply": 10})

    assert before_threshold.stalled is False
    assert before_threshold.urgency == "low"

    assert at_stalled_threshold.stalled is True
    assert at_stalled_threshold.urgency == "medium"
    assert at_stalled_threshold.trigger_reason == "no_reply_5_days"
    assert at_stalled_threshold.confidence == 0.9

    assert at_high_urgency_threshold.stalled is True
    assert at_high_urgency_threshold.urgency == "high"
