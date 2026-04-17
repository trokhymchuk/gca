import subprocess
import textwrap
from pathlib import Path

import pytest

from git_commit_analyzer.parser import _parse_trailers, _strip_trailer_block, get_commits

_TRAILER_SEP = "\x02"


def test_strip_trailer_block_no_trailers():
    body = "This is a description.\n\nWith multiple paragraphs."
    assert _strip_trailer_block(body) == body.strip()


def test_strip_trailer_block_with_trailers():
    body = textwrap.dedent("""\
        Fix the bug in the parser.

        More details here.

        Fixes: #42
        Reviewed-by: Alice <alice@example.com>
        Co-authored-by: Bob <bob@example.com>
    """)
    assert _strip_trailer_block(body) == "Fix the bug in the parser.\n\nMore details here."


def test_parse_trailers_multiple():
    raw = _TRAILER_SEP.join([
        "Fixes: #42",
        "Reviewed-by: Alice <alice@example.com>",
        "Co-authored-by: Bob <bob@example.com>",
    ])
    trailers = _parse_trailers(raw)
    assert len(trailers) == 3
    assert trailers[0].token == "Fixes"
    assert trailers[0].value == "#42"
    assert trailers[1].token == "Reviewed-by"
    assert trailers[2].token == "Co-authored-by"


def test_parse_trailers_empty():
    assert _parse_trailers("") == []


@pytest.fixture()
def git_repo(tmp_path: Path) -> Path:
    subprocess.run(["git", "init", "-b", "main"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=tmp_path, check=True, capture_output=True)
    return tmp_path


def _make_commit(repo: Path, message: str) -> str:
    (repo / "file.txt").write_text(message)
    subprocess.run(["git", "add", "."], cwd=repo, check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=repo, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True, text=True, check=True
    ).stdout.strip()


def test_get_single_commit(git_repo: Path):
    _make_commit(git_repo, "feat: add initial feature")
    commits = get_commits(git_repo)
    assert len(commits) == 1
    assert commits[0].subject == "feat: add initial feature"
    assert commits[0].author_email == "test@example.com"
    assert commits[0].is_fixup is False


def test_get_commits_range(git_repo: Path):
    _make_commit(git_repo, "chore: initial commit")
    base_sha = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=git_repo, capture_output=True, text=True, check=True
    ).stdout.strip()

    _make_commit(git_repo, "feat: feature A")
    _make_commit(git_repo, "fixup! feat: feature A")

    commits = get_commits(git_repo, base_ref=base_sha)
    assert len(commits) == 2
    subjects = [c.subject for c in commits]
    assert "feat: feature A" in subjects
    assert "fixup! feat: feature A" in subjects

    fixup = next(c for c in commits if c.subject.startswith("fixup!"))
    assert fixup.is_fixup is True


def test_commit_with_trailers(git_repo: Path):
    message = textwrap.dedent("""\
        feat: implement new thing

        Some longer explanation.

        Fixes: #99
        Reviewed-by: Alice <alice@example.com>
    """)
    _make_commit(git_repo, message)
    commits = get_commits(git_repo)
    assert len(commits) == 1
    c = commits[0]
    assert c.subject == "feat: implement new thing"
    assert "Some longer explanation." in c.description
    assert len(c.trailers) == 2
    assert c.trailer("Fixes") == ["#99"]
    assert c.trailer("reviewed-by") == ["Alice <alice@example.com>"]
