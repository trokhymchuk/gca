"""Integration tests for LlmChecker against a real model.

These tests are SKIPPED automatically when:
  - the required backend library is not installed, OR
  - the config file is not present at the project root.

Select which config to test against with the GCA_LLM_CONFIG env var:

    GCA_LLM_CONFIG=llm-transformers-config.yml pytest tests/test_llm_integration.py -v
    GCA_LLM_CONFIG=llm-config.yml             pytest tests/test_llm_integration.py -v

For an HTTP API backend (openai/anthropic/deepseek/gemini), point at its config
and export the matching API key, e.g. for Gemini:

    export GEMINI_API_KEY=...
    GCA_LLM_CONFIG=llm-api-config.yml pytest tests/test_llm_integration.py -v -m integration

API-backend tests are skipped automatically when no API key can be resolved.

Defaults to llm-config.yml when the variable is not set.

The model is loaded once per session so all commits share one load cost.
Commit fixtures are loaded from tests/commits/*.json.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from git_commit_analyzer import GitCommit, LlmChecker
from git_commit_analyzer.rules import load_config

# ---------------------------------------------------------------------------
# Config path — override via GCA_LLM_CONFIG env var
# ---------------------------------------------------------------------------

_ROOT = Path(__file__).parent.parent
_CONFIG_NAME = os.environ.get("GCA_LLM_CONFIG", "llm-llama-cpp-config.yml")
_CONFIG_PATH = _ROOT / _CONFIG_NAME
_COMMITS_DIR = Path(__file__).parent / "commits"

# ---------------------------------------------------------------------------
# Backend availability checks
# ---------------------------------------------------------------------------

_backend = "llama-cpp"  # default; updated below after reading config
_llm_cfg: dict = {}
if _CONFIG_PATH.exists():
    try:
        import yaml

        _raw = yaml.safe_load(_CONFIG_PATH.read_text())
        _llm_cfg = (_raw or {}).get("config", {}).get("llm", {}) or {}
        _backend = _llm_cfg.get("backend", "llama-cpp")
    except Exception:
        pass

_LLAMA_AVAILABLE = False
_TRANSFORMERS_AVAILABLE = False
try:
    import llama_cpp  # noqa: F401

    _LLAMA_AVAILABLE = True
except ImportError:
    pass
try:
    import transformers  # noqa: F401
    import torch  # noqa: F401

    _TRANSFORMERS_AVAILABLE = True
except ImportError:
    pass

# HTTP API backends need no library — they need a resolvable API key instead.
_API_KEY_ENV = {
    "openai": "OPENAI_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
}


def _api_key_available() -> bool:
    if _llm_cfg.get("api_key"):
        return True
    env_name = _llm_cfg.get("api_key_env") or _API_KEY_ENV.get(_backend, "")
    return bool(env_name and os.environ.get(env_name))


_backend_available = (
    (_backend == "llama-cpp" and _LLAMA_AVAILABLE)
    or (_backend == "transformers" and _TRANSFORMERS_AVAILABLE)
    or (_backend in _API_KEY_ENV and _api_key_available())
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _CONFIG_PATH.exists(), reason=f"{_CONFIG_NAME} not found"),
    pytest.mark.skipif(
        not _backend_available,
        reason=(
            f"backend '{_backend}' unavailable "
            "(dependencies not installed or API key not set)"
        ),
    ),
]

# ---------------------------------------------------------------------------
# Load commit fixtures from JSON files
# ---------------------------------------------------------------------------

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _load_commits(path: Path) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    data = json.loads(path.read_text())
    good = [(c["subject"], c["description"]) for c in data.get("good", [])]
    bad = [(c["subject"], c["description"]) for c in data.get("bad", [])]
    return good, bad


def _collect_commits() -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
    good: list[tuple[str, str]] = []
    bad: list[tuple[str, str]] = []
    for path in sorted(_COMMITS_DIR.glob("*.json")):
        g, b = _load_commits(path)
        good.extend(g)
        bad.extend(b)
    return good, bad


GOOD_COMMITS, BAD_COMMITS = _collect_commits()

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def llm_checker() -> LlmChecker:
    """Load the model once for the entire test session."""
    rf = load_config(_CONFIG_PATH)
    checker = rf.ruleset.rules[0].checkers[0]
    assert isinstance(checker, LlmChecker)
    checker._get_backend()  # eagerly load so timing shows in fixture, not first test
    return checker


def make_commit(subject: str, description: str = "") -> GitCommit:
    return GitCommit(
        sha="a" * 40,
        subject=subject,
        body=description,
        description=description,
        trailers=[],
        parent_shas=[],
        changed_files=[],
        author_name="Test Author",
        author_email="author@example.com",
        author_date=_NOW,
        committer_name="Test Author",
        committer_email="author@example.com",
        committer_date=_NOW,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestLlmWithGoodCommits:
    @pytest.mark.parametrize("subject,description", GOOD_COMMITS)
    def test_good_commit_passes(
        self, llm_checker: LlmChecker, subject: str, description: str
    ):
        result = llm_checker(make_commit(subject, description))
        assert result.passed is True, (
            f"Expected PASS for good commit {subject!r}\nLLM response: {result.message}"
        )


class TestLlmWithBadCommits:
    @pytest.mark.parametrize("subject,description", BAD_COMMITS)
    def test_bad_commit_fails(
        self, llm_checker: LlmChecker, subject: str, description: str
    ):
        result = llm_checker(make_commit(subject, description))
        assert result.passed is False, (
            f"Expected FAIL for bad commit {subject!r}\nLLM response: {result.message}"
        )
