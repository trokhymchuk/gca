"""Integration tests for LlmChecker against a real local LLM.

These tests are SKIPPED automatically when:
  - llama-cpp-python is not installed, OR
  - llm-config.yml is not present at the project root.

To run them:
    pip install 'gca[llm]'
    # ensure llm-config.yml exists and points to a valid model
    pytest tests/test_llm_integration.py -v

The model is loaded once per session so all commits share one load cost.
Commit fixtures are loaded from tests/commits/main.json and tests/commits/extra.json.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from git_commit_analyzer import GitCommit, LlmChecker
from git_commit_analyzer.rules import load_config

# ---------------------------------------------------------------------------
# Config and skip guards
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).parent.parent / "llm-config.yml"
_COMMITS_DIR = Path(__file__).parent / "commits"

try:
    import llama_cpp  # noqa: F401

    _LLAMA_AVAILABLE = True
except ImportError:
    _LLAMA_AVAILABLE = False

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _LLAMA_AVAILABLE, reason="llama-cpp-python not installed"),
    pytest.mark.skipif(not _CONFIG_PATH.exists(), reason="llm-config.yml not found"),
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
    checker._get_llm()  # eagerly load so timing shows in fixture, not first test
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
