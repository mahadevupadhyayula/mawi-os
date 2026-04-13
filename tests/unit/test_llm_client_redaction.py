import pytest

from agents.llm_client import LLMRequest, generate_json, redact_prompt_text


def test_redact_prompt_text_scrubs_common_sensitive_patterns() -> None:
    prompt = (
        "Contact jane.doe@example.com or +1 (415) 555-0101. "
        "Customer numeric id is 123456789012."
    )
    redacted, changed = redact_prompt_text(prompt, enabled=True)

    assert changed is True
    assert "jane.doe@example.com" not in redacted
    assert "123456789012" not in redacted
    assert "555-0101" not in redacted
    assert "<redacted_email>" in redacted
    assert "<redacted_phone>" in redacted
    assert "<redacted_numeric_id>" in redacted


def test_generate_json_applies_redaction_before_provider_submission(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAWI_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MAWI_LLM_REDACTION_ENABLED", "true")

    captured: dict[str, str] = {}

    def _mock_call(**kwargs):
        captured["prompt"] = kwargs["prompt"]
        return {"choices": [{"message": {"content": '{"answer":"ok"}'}}]}

    monkeypatch.setattr("agents.llm_client._call_openai_chat_completions", _mock_call)

    result = generate_json(
        LLMRequest(
            prompt="Email me at jane.doe@example.com and call +1 415 555 0101",
            required_fields=["answer"],
            model="gpt-test",
        )
    )

    assert result.error is None
    assert result.redaction_occurred is True
    assert "jane.doe@example.com" not in captured["prompt"]
    assert "555 0101" not in captured["prompt"]


def test_generate_json_passthrough_when_redaction_explicitly_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAWI_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MAWI_LLM_REDACTION_ENABLED", "false")

    captured: dict[str, str] = {}
    prompt = "Send to jane.doe@example.com with ticket 1234567890"

    def _mock_call(**kwargs):
        captured["prompt"] = kwargs["prompt"]
        return {"choices": [{"message": {"content": '{"answer":"ok"}'}}]}

    monkeypatch.setattr("agents.llm_client._call_openai_chat_completions", _mock_call)

    result = generate_json(
        LLMRequest(
            prompt=prompt,
            required_fields=["answer"],
            model="gpt-test",
        )
    )

    assert result.error is None
    assert result.redaction_occurred is False
    assert captured["prompt"] == prompt
