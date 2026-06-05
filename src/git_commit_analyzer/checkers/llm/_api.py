"""Shared helpers for HTTP API-based LLM backends (OpenAI, Anthropic, DeepSeek).

These backends talk to a hosted chat API over plain HTTP using the standard
library only, so no provider SDK needs to be installed.
"""

import json
import os
import urllib.error
import urllib.request
from typing import Any

from ...config import LlmConfig


def resolve_api_key(config: LlmConfig, default_env: str) -> str:
    """Resolve the API token for an HTTP backend from config or the environment.

    Resolution order:
      1. :attr:`~git_commit_analyzer.config.LlmConfig.api_key` when set
         (a literal token).
      2. The environment variable named by
         :attr:`~git_commit_analyzer.config.LlmConfig.api_key_env` when set.
      3. The provider's default environment variable (*default_env*).

    Args:
        config: The LLM configuration.
        default_env: Environment variable consulted when neither ``api_key``
            nor ``api_key_env`` is provided.

    Returns:
        The resolved API token.

    Raises:
        ValueError: If no token can be resolved.
    """
    if config.api_key:
        return config.api_key
    env_name = config.api_key_env or default_env
    key = os.environ.get(env_name)
    if not key:
        raise ValueError(
            f"No API key found for the {config.backend!r} backend. Set 'api_key' "
            f"in the config.llm section, export the {env_name} environment "
            "variable, or set 'api_key_env' to the variable holding your token."
        )
    return key


def post_json(
    url: str, headers: dict[str, str], payload: dict[str, Any], timeout: int
) -> dict[str, Any]:
    """POST *payload* as JSON to *url* and return the decoded JSON response.

    Raises:
        RuntimeError: If the request fails or returns a non-2xx status.
    """
    data = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"API request to {url} failed ({exc.code}): {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"API request to {url} failed: {exc.reason}") from exc
