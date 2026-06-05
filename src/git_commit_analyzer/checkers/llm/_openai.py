from ...config import LlmConfig
from ._api import post_json, resolve_api_key
from ._base import LlmBackend


class OpenAiBackend(LlmBackend):
    """LLM backend for the OpenAI chat-completions API and compatible servers.

    The rendered prompt is sent as a single ``user`` message and the model's
    reply text is returned verbatim (the :class:`~..LlmChecker` parses the
    ``PASS``/``FAIL`` verdict from it).

    The API token is resolved by :func:`._api.resolve_api_key` from
    ``config.api_key``, ``config.api_key_env`` or the provider default
    environment variable.  No provider SDK is required — requests go over
    plain HTTP using the standard library.
    """

    default_base_url = "https://api.openai.com/v1"
    default_api_key_env = "OPENAI_API_KEY"
    provider_name = "openai"

    def __init__(self, config: LlmConfig) -> None:
        if not config.model:
            raise ValueError(
                f"The {self.provider_name!r} backend requires 'model' to be set "
                "in the config.llm section (e.g. model: gpt-4o-mini)."
            )
        self._model = config.model
        self._api_key = resolve_api_key(config, self.default_api_key_env)
        self._base_url = (config.base_url or self.default_base_url).rstrip("/")
        self._timeout = config.request_timeout
        self._temperature = config.temperature

    def generate(self, prompt: str, max_tokens: int, stop: list[str]) -> str:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
        }
        if stop:
            payload["stop"] = stop
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        data = post_json(
            f"{self._base_url}/chat/completions", headers, payload, self._timeout
        )
        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected API response shape: {data!r}") from exc


class DeepSeekBackend(OpenAiBackend):
    """DeepSeek chat API backend.

    DeepSeek exposes an OpenAI-compatible endpoint, so this reuses
    :class:`OpenAiBackend` and only changes the default base URL and the
    default API-key environment variable.
    """

    default_base_url = "https://api.deepseek.com/v1"
    default_api_key_env = "DEEPSEEK_API_KEY"
    provider_name = "deepseek"
