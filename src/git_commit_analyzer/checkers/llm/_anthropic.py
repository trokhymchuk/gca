from ...config import LlmConfig
from ._api import post_json, resolve_api_key
from ._base import LlmBackend


class AnthropicBackend(LlmBackend):
    """LLM backend for the Anthropic Messages API.

    The rendered prompt is sent as a single ``user`` message and the
    concatenated text of the response content blocks is returned (the
    :class:`~..LlmChecker` parses the ``PASS``/``FAIL`` verdict from it).

    The API token is resolved by :func:`._api.resolve_api_key` from
    ``config.api_key``, ``config.api_key_env`` or ``ANTHROPIC_API_KEY``.
    No provider SDK is required — requests go over plain HTTP using the
    standard library.
    """

    default_base_url = "https://api.anthropic.com/v1"
    default_api_key_env = "ANTHROPIC_API_KEY"
    anthropic_version = "2023-06-01"
    provider_name = "anthropic"

    def __init__(self, config: LlmConfig) -> None:
        if not config.model:
            raise ValueError(
                "The 'anthropic' backend requires 'model' to be set in the "
                "config.llm section (e.g. model: claude-3-5-sonnet-latest)."
            )
        self._model = config.model
        self._api_key = resolve_api_key(config, self.default_api_key_env)
        self._base_url = (config.base_url or self.default_base_url).rstrip("/")
        self._timeout = config.request_timeout
        self._temperature = config.temperature

    def generate(self, prompt: str, max_tokens: int, stop: list[str]) -> str:
        payload: dict[str, object] = {
            "model": self._model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if stop:
            payload["stop_sequences"] = stop
        if self._temperature is not None:
            payload["temperature"] = self._temperature
        headers = {
            "x-api-key": self._api_key,
            "anthropic-version": self.anthropic_version,
            "Content-Type": "application/json",
        }
        data = post_json(f"{self._base_url}/messages", headers, payload, self._timeout)
        try:
            blocks = data["content"]
            text = "".join(
                block.get("text", "") for block in blocks if block.get("type") == "text"
            )
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"Unexpected API response shape: {data!r}") from exc
        return text.strip()
