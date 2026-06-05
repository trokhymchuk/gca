"""Tests for the HTTP API LLM backends: openai, deepseek, anthropic, gemini.

No real network calls are made — ``_api.post_json`` is patched in every test,
and API keys are supplied via monkeypatched environment variables or config.
"""

from pathlib import Path
from unittest.mock import patch

import pytest

from git_commit_analyzer import load_config
from git_commit_analyzer.checkers.llm import _load_backend
from git_commit_analyzer.checkers.llm._anthropic import AnthropicBackend
from git_commit_analyzer.checkers.llm._api import resolve_api_key
from git_commit_analyzer.checkers.llm._gemini import GeminiBackend
from git_commit_analyzer.checkers.llm._openai import DeepSeekBackend, OpenAiBackend
from git_commit_analyzer.config import LlmConfig


def make_config(backend: str, **overrides) -> LlmConfig:
    base = dict(prompt="Review: {commit}", backend=backend, model="some-model")
    base.update(overrides)
    return LlmConfig(**base)


# ---------------------------------------------------------------------------
# resolve_api_key
# ---------------------------------------------------------------------------


class TestResolveApiKey:
    def test_literal_api_key_wins(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "from-env")
        config = make_config("openai", api_key="from-config")
        assert resolve_api_key(config, "OPENAI_API_KEY") == "from-config"

    def test_api_key_env_name_is_used(self, monkeypatch):
        monkeypatch.setenv("MY_TOKEN", "secret-123")
        config = make_config("openai", api_key_env="MY_TOKEN")
        assert resolve_api_key(config, "OPENAI_API_KEY") == "secret-123"

    def test_falls_back_to_default_env(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "default-env-token")
        config = make_config("openai")
        assert resolve_api_key(config, "OPENAI_API_KEY") == "default-env-token"

    def test_missing_key_raises(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        config = make_config("openai")
        with pytest.raises(ValueError, match="No API key"):
            resolve_api_key(config, "OPENAI_API_KEY")


# ---------------------------------------------------------------------------
# OpenAI / DeepSeek
# ---------------------------------------------------------------------------


class TestOpenAiBackend:
    def _backend(self, **overrides) -> OpenAiBackend:
        return OpenAiBackend(make_config("openai", api_key="k", **overrides))

    def test_requires_model(self):
        with pytest.raises(ValueError, match="requires 'model'"):
            OpenAiBackend(LlmConfig(prompt="{commit}", backend="openai", api_key="k"))

    def test_generate_posts_and_returns_content(self):
        backend = self._backend()
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return {"choices": [{"message": {"content": "PASS looks good "}}]}

        with patch(
            "git_commit_analyzer.checkers.llm._openai.post_json", side_effect=fake_post
        ):
            result = backend.generate("the prompt", 60, ["<|im_end|>"])

        assert result == "PASS looks good"
        assert captured["url"] == "https://api.openai.com/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer k"
        assert captured["payload"]["model"] == "some-model"
        assert captured["payload"]["messages"][0]["content"] == "the prompt"
        assert captured["payload"]["max_tokens"] == 60
        assert captured["payload"]["stop"] == ["<|im_end|>"]

    def test_custom_base_url_trailing_slash_stripped(self):
        backend = self._backend(base_url="https://gateway.local/v1/")
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["url"] = url
            return {"choices": [{"message": {"content": "PASS"}}]}

        with patch(
            "git_commit_analyzer.checkers.llm._openai.post_json", side_effect=fake_post
        ):
            backend.generate("p", 10, [])
        assert captured["url"] == "https://gateway.local/v1/chat/completions"

    def test_stop_omitted_when_empty(self):
        backend = self._backend()
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["payload"] = payload
            return {"choices": [{"message": {"content": "PASS"}}]}

        with patch(
            "git_commit_analyzer.checkers.llm._openai.post_json", side_effect=fake_post
        ):
            backend.generate("p", 10, [])
        assert "stop" not in captured["payload"]

    def test_unexpected_response_raises(self):
        backend = self._backend()
        with patch(
            "git_commit_analyzer.checkers.llm._openai.post_json",
            return_value={"error": "nope"},
        ):
            with pytest.raises(RuntimeError, match="Unexpected API response"):
                backend.generate("p", 10, [])

    def test_temperature_sent_when_set(self):
        backend = self._backend(temperature=0)
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["payload"] = payload
            return {"choices": [{"message": {"content": "PASS"}}]}

        with patch(
            "git_commit_analyzer.checkers.llm._openai.post_json", side_effect=fake_post
        ):
            backend.generate("p", 10, [])
        assert captured["payload"]["temperature"] == 0

    def test_temperature_omitted_when_none(self):
        backend = self._backend()
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["payload"] = payload
            return {"choices": [{"message": {"content": "PASS"}}]}

        with patch(
            "git_commit_analyzer.checkers.llm._openai.post_json", side_effect=fake_post
        ):
            backend.generate("p", 10, [])
        assert "temperature" not in captured["payload"]


class TestDeepSeekBackend:
    def test_defaults(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "ds-key")
        backend = DeepSeekBackend(make_config("deepseek"))
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["url"] = url
            captured["headers"] = headers
            return {"choices": [{"message": {"content": "FAIL too vague"}}]}

        with patch(
            "git_commit_analyzer.checkers.llm._openai.post_json", side_effect=fake_post
        ):
            result = backend.generate("p", 10, [])
        assert result == "FAIL too vague"
        assert captured["url"] == "https://api.deepseek.com/v1/chat/completions"
        assert captured["headers"]["Authorization"] == "Bearer ds-key"


# ---------------------------------------------------------------------------
# Anthropic
# ---------------------------------------------------------------------------


class TestAnthropicBackend:
    def test_requires_model(self):
        with pytest.raises(ValueError, match="requires 'model'"):
            AnthropicBackend(
                LlmConfig(prompt="{commit}", backend="anthropic", api_key="k")
            )

    def test_generate_posts_messages_and_concatenates_text(self):
        backend = AnthropicBackend(make_config("anthropic", api_key="ak"))
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return {
                "content": [
                    {"type": "text", "text": "PASS "},
                    {"type": "text", "text": "well done"},
                    {"type": "thinking", "text": "ignored"},
                ]
            }

        with patch(
            "git_commit_analyzer.checkers.llm._anthropic.post_json",
            side_effect=fake_post,
        ):
            result = backend.generate("the prompt", 50, ["STOP"])

        assert result == "PASS well done"
        assert captured["url"] == "https://api.anthropic.com/v1/messages"
        assert captured["headers"]["x-api-key"] == "ak"
        assert captured["headers"]["anthropic-version"] == "2023-06-01"
        assert captured["payload"]["max_tokens"] == 50
        assert captured["payload"]["stop_sequences"] == ["STOP"]

    def test_unexpected_response_raises(self):
        backend = AnthropicBackend(make_config("anthropic", api_key="ak"))
        with patch(
            "git_commit_analyzer.checkers.llm._anthropic.post_json",
            return_value={"oops": True},
        ):
            with pytest.raises(RuntimeError, match="Unexpected API response"):
                backend.generate("p", 10, [])


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


class TestGeminiBackend:
    def test_requires_model(self):
        with pytest.raises(ValueError, match="requires 'model'"):
            GeminiBackend(LlmConfig(prompt="{commit}", backend="gemini", api_key="k"))

    def test_generate_posts_and_returns_text(self):
        backend = GeminiBackend(
            make_config("gemini", api_key="gk", model="gemini-2.0-flash")
        )
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["url"] = url
            captured["headers"] = headers
            captured["payload"] = payload
            return {
                "candidates": [
                    {"content": {"parts": [{"text": "PASS "}, {"text": "great"}]}}
                ]
            }

        with patch(
            "git_commit_analyzer.checkers.llm._gemini.post_json", side_effect=fake_post
        ):
            result = backend.generate("the prompt", 40, ["END"])

        assert result == "PASS great"
        assert captured["url"] == (
            "https://generativelanguage.googleapis.com/v1beta/"
            "models/gemini-2.0-flash:generateContent"
        )
        assert captured["headers"]["x-goog-api-key"] == "gk"
        assert captured["payload"]["generationConfig"]["maxOutputTokens"] == 40
        assert captured["payload"]["generationConfig"]["stopSequences"] == ["END"]
        assert "temperature" not in captured["payload"]["generationConfig"]
        assert captured["payload"]["contents"][0]["parts"][0]["text"] == "the prompt"

    def test_temperature_nested_in_generation_config(self):
        backend = GeminiBackend(make_config("gemini", api_key="gk", temperature=0))
        captured = {}

        def fake_post(url, headers, payload, timeout):
            captured["payload"] = payload
            return {"candidates": [{"content": {"parts": [{"text": "PASS"}]}}]}

        with patch(
            "git_commit_analyzer.checkers.llm._gemini.post_json", side_effect=fake_post
        ):
            backend.generate("p", 10, [])
        assert captured["payload"]["generationConfig"]["temperature"] == 0

    def test_unexpected_response_raises(self):
        backend = GeminiBackend(make_config("gemini", api_key="gk"))
        with patch(
            "git_commit_analyzer.checkers.llm._gemini.post_json",
            return_value={"candidates": []},
        ):
            with pytest.raises(RuntimeError, match="Unexpected API response"):
                backend.generate("p", 10, [])


# ---------------------------------------------------------------------------
# _load_backend dispatch
# ---------------------------------------------------------------------------


class TestLoadBackendDispatch:
    def test_openai(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "x")
        assert isinstance(_load_backend(make_config("openai")), OpenAiBackend)

    def test_deepseek(self, monkeypatch):
        monkeypatch.setenv("DEEPSEEK_API_KEY", "x")
        assert isinstance(_load_backend(make_config("deepseek")), DeepSeekBackend)

    def test_anthropic(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "x")
        assert isinstance(_load_backend(make_config("anthropic")), AnthropicBackend)

    def test_gemini(self, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "x")
        assert isinstance(_load_backend(make_config("gemini")), GeminiBackend)

    def test_unknown_backend_lists_all_supported(self):
        with pytest.raises(ValueError, match="gemini"):
            _load_backend(make_config("nope"))


# ---------------------------------------------------------------------------
# Config parsing for the new fields
# ---------------------------------------------------------------------------


class TestApiConfigParsing:
    def test_api_fields_parsed_from_yaml(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
config:
  llm:
    backend: openai
    model: gpt-4o-mini
    api_key_env: MY_OPENAI_KEY
    base_url: https://gateway.local/v1
    request_timeout: 30
    temperature: 0
    prompt: "Review: {commit}"
rules: []
""")
        llm = load_config(yaml_file).config.llm
        assert llm is not None
        assert llm.backend == "openai"
        assert llm.model == "gpt-4o-mini"
        assert llm.api_key_env == "MY_OPENAI_KEY"
        assert llm.base_url == "https://gateway.local/v1"
        assert llm.request_timeout == 30
        assert llm.temperature == 0

    def test_api_fields_default_to_none(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
config:
  llm:
    repo_id: "test/model"
    filename: "*.gguf"
    prompt: "{commit}"
rules: []
""")
        llm = load_config(yaml_file).config.llm
        assert llm is not None
        assert llm.model is None
        assert llm.api_key is None
        assert llm.api_key_env is None
        assert llm.base_url is None
        assert llm.request_timeout == 60
        assert llm.temperature is None
