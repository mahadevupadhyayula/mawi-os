from evaluation.feedback_policy import gate_memory_evidence, summarize_adaptation


def test_stage_one_passes_through_evidence() -> None:
    evidence = [{"snippet": "ROI works", "quality_score": 0.05}]
    selected, reason = gate_memory_evidence(stage=1, evidence=evidence)

    assert selected == evidence
    assert reason == "stage_1_basic_pass_through"


def test_stage_two_blocks_when_peak_quality_low() -> None:
    evidence = [{"snippet": "weak", "quality_score": 0.19}]
    selected, reason = gate_memory_evidence(stage=2, evidence=evidence)

    assert selected == []
    assert reason == "stage_2_blocked_low_peak_quality"


def test_stage_three_requires_count_and_average_quality() -> None:
    weak = [{"snippet": "a", "quality_score": 0.4}]
    selected_weak, reason_weak = gate_memory_evidence(stage=3, evidence=weak)
    assert selected_weak == []
    assert reason_weak == "stage_3_blocked_insufficient_items"

    evidence = [
        {"snippet": "a", "quality_score": 0.3},
        {"snippet": "b", "quality_score": 0.31},
    ]
    selected, reason = gate_memory_evidence(stage=3, evidence=evidence)
    assert selected == evidence
    assert reason == "stage_3_pass_quality_gate"


def test_summarize_adaptation_reports_selection_and_quality() -> None:
    summary = summarize_adaptation(
        stage=2,
        selected_evidence=[{"snippet": "x", "quality_score": 0.2}, {"snippet": "y", "quality_score": 0.3}],
        gate_reason="stage_2_pass_quality_gate",
    )
    assert summary["stage"] == 2
    assert summary["selected_items"] == 2
    assert summary["avg_quality_score"] == 0.25
    assert summary["adaptation_enabled"] is True
