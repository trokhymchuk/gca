from ...config import LlmConfig
from ._api import post_json, resolve_api_key
from ._base import LlmBackend


class GeminiBackend(LlmBackend):
    """LLM backend for the Google Gemini (Generative Language) API.

    The rendered prompt is sent as a single ``user`` content part and the
    concatenated text of the response parts is returned (the
    :class:`~..LlmChecker` parses the ``PASS``/``FAIL`` verdict from it).

    The API token is resolved by :func:`._api.resolve_api_key` from
    ``config.api_key``, ``config.api_key_env`` or ``GEMINI_API_KEY`` and sent
    via the ``x-goog-api-key`` header.  No provider SDK is required — requests
    go over plain HTTP using the standard library.
    """

    default_base_url = "https://generativelanguage.googleapis.com/v1beta"
    default_api_key_env = "GEMINI_API_KEY"
    provider_name = "gemini"

    def __init__(self, config: LlmConfig) -> None:
        if not config.model:
            raise ValueError(
                "The 'gemini' backend requires 'model' to be set in the "
                "config.llm section (e.g. model: gemini-2.0-flash)."
            )
        self._model = config.model
        self._api_key = resolve_api_key(config, self.default_api_key_env)
        self._base_url = (config.base_url or self.default_base_url).rstrip("/")
        self._timeout = config.request_timeout
        self._temperature = config.temperature

    def generate(self, prompt: str, max_tokens: int, stop: list[str]) -> str:
        generation_config: dict[str, object] = {"maxOutputTokens": max_tokens}
        if stop:
            generation_config["stopSequences"] = stop
        if self._temperature is not None:
            generation_config["temperature"] = self._temperature
        payload = {
            "contents": [{"role": "user", "parts": [{"text": prompt}]}],
            "generationConfig": generation_config,
        }
        headers = {
            "x-goog-api-key": self._api_key,
            "Content-Type": "application/json",
        }
        url = f"{self._base_url}/models/{self._model}:generateContent"
        data = post_json(url, headers, payload, self._timeout)
        try:
            parts = data["candidates"][0]["content"]["parts"]
            text = "".join(part.get("text", "") for part in parts)
        except (KeyError, IndexError, TypeError) as exc:
            raise RuntimeError(f"Unexpected API response shape: {data!r}") from exc
        return text.strip()
