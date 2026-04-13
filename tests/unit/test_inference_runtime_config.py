import logging

from agents.inference import resolve_model_output
from agents.llm_client import LLMResult


def test_resolve_model_output_passes_runtime_retry_and_timeout_to_request(monkeypatch) -> None:
    captured = {}

    def _mock_generate_json(request):
        captured["timeout_sec"] = request.timeout_sec
        captured["max_retries"] = request.max_retries
        return LLMResult(
            raw_text='{"field":"ok","reasoning":"ok","confidence":0.9}',
            payload={"field": "ok", "reasoning": "ok", "confidence": 0.9},
            latency_ms=5,
            provider="openai",
            model=request.model,
            error=None,
            token_usage=None,
        )

    monkeypatch.setattr("agents.inference.llm_client.generate_json", _mock_generate_json)

    resolution = resolve_model_output(
        llm_enabled=True,
        deterministic_json_string='{"field":"fallback"}',
        prompt_text="prompt",
        required_fields=["field", "reasoning", "confidence"],
        stage_name="test_stage",
        model="gpt-test",
        timeout_sec=41.5,
        max_retries=4,
        logger=logging.getLogger("test"),
    )

    assert resolution.model_output == '{"field": "ok", "reasoning": "ok", "confidence": 0.9}'
    assert captured == {"timeout_sec": 41.5, "max_retries": 4}
