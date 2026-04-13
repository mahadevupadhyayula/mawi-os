import pytest

from agents.llm_client import LLMRequest, generate_json


def test_generate_json_prefers_explicit_retry_settings_over_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAWI_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MAWI_LLM_MAX_RETRIES", "7")
    monkeypatch.setenv("MAWI_LLM_RETRY_BACKOFF_SEC", "9.5")

    call_count = {"count": 0}
    sleep_calls: list[tuple[float, int]] = []

    def _mock_call(**_kwargs):
        call_count["count"] += 1
        return {
            "choices": [{"message": {"content": "not-json"}}],
        }

    def _mock_sleep(backoff_sec: float, attempt: int) -> None:
        sleep_calls.append((backoff_sec, attempt))

    monkeypatch.setattr("agents.llm_client._call_openai_chat_completions", _mock_call)
    monkeypatch.setattr("agents.llm_client._sleep_before_retry", _mock_sleep)

    result = generate_json(
        LLMRequest(
            prompt="return json",
            required_fields=["answer"],
            model="gpt-test",
            max_retries=1,
            retry_backoff_sec=0.25,
        )
    )

    assert result.error == "invalid_json"
    assert call_count["count"] == 2
    assert sleep_calls == [(0.25, 0)]


def test_generate_json_uses_environment_retry_settings_as_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MAWI_LLM_PROVIDER", "openai")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("MAWI_LLM_MAX_RETRIES", "3")
    monkeypatch.setenv("MAWI_LLM_RETRY_BACKOFF_SEC", "0.75")

    call_count = {"count": 0}
    sleep_calls: list[tuple[float, int]] = []

    def _mock_call(**_kwargs):
        call_count["count"] += 1
        return {
            "choices": [{"message": {"content": "not-json"}}],
        }

    def _mock_sleep(backoff_sec: float, attempt: int) -> None:
        sleep_calls.append((backoff_sec, attempt))

    monkeypatch.setattr("agents.llm_client._call_openai_chat_completions", _mock_call)
    monkeypatch.setattr("agents.llm_client._sleep_before_retry", _mock_sleep)

    result = generate_json(
        LLMRequest(
            prompt="return json",
            required_fields=["answer"],
            model="gpt-test",
            max_retries=None,
            retry_backoff_sec=None,
        )
    )

    assert result.error == "invalid_json"
    assert call_count["count"] == 4
    assert sleep_calls == [(0.75, 0), (0.75, 1), (0.75, 2)]
