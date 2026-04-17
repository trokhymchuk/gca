"""Git log parsing utilities.

Fetches commit metadata by invoking ``git log`` with a structured format string,
then deserialises the raw output into :class:`~git_commit_analyzer.models.GitCommit`
objects. Two separate ``git log`` calls are made per invocation: one for commit
metadata (subject, body, trailers, dates, …) and one for changed-file lists.
"""

import subprocess
from datetime import datetime
from pathlib import Path

from .models import GitCommit, Trailer

# Field and record separators — git expands %xNN in the output;
# using the escape form avoids passing actual control bytes as CLI args.
_FIELD_SEP = "\x00"
_TRAILER_SEP = "\x02"  # separates individual trailers within the trailers field
_RECORD_SEP = "\x01"

_GIT_FIELD_SEP = "%x00"
_GIT_TRAILER_SEP = "%x02"
_GIT_RECORD_SEP = "%x01"

# Trailers are extracted by git itself via %(trailers:separator=<sep>).
# %(trailers:only,separator=...) emits only lines git recognises as trailers,
# respecting gitconfig trailer settings (custom separators, key aliases, etc.).
# %b is kept for the raw body; description is derived by stripping the trailer block.
_FORMAT = (
    _GIT_FIELD_SEP.join(
        [
            "%H",
            "%ae",
            "%an",
            "%aI",
            "%ce",
            "%cn",
            "%cI",
            "%s",
            "%b",
            "%P",
            f"%(trailers:only,separator={_GIT_TRAILER_SEP})",
        ]
    )
    + _GIT_RECORD_SEP
)


def _parse_trailers(raw: str) -> list[Trailer]:
    """Parse the raw trailer field produced by ``%(trailers:only,separator=…)``.

    Args:
        raw: STX-separated string of ``Token: value`` lines as emitted by git.

    Returns:
        Ordered list of :class:`~git_commit_analyzer.models.Trailer` objects.
        Lines without a ``: `` separator are silently skipped.
    """
    trailers = []
    for line in raw.split(_TRAILER_SEP):
        line = line.strip()
        if ": " in line:
            token, _, value = line.partition(": ")
            trailers.append(Trailer(token=token.strip(), value=value.strip()))
    return trailers


def _strip_trailer_block(body: str) -> str:
    """Return *body* with the trailing trailer block and its preceding blank line removed.

    Args:
        body: Raw commit body that may end with a trailer block.

    Returns:
        Body text with the trailer block stripped, or the original text if no
        trailer block is found.
    """
    lines = body.splitlines()
    i = len(lines) - 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    while i >= 0 and ": " in lines[i] and not lines[i].startswith(" "):
        i -= 1
    while i >= 0 and not lines[i].strip():
        i -= 1
    return "\n".join(lines[: i + 1]).strip()


def _parse_record(record: str, changed_files: dict[str, list[str]]) -> GitCommit | None:
    """Deserialise a single NUL-delimited commit record into a :class:`GitCommit`.

    Args:
        record: Raw text of one commit record as produced by ``git log --format``,
            with fields separated by ``\\x00`` and the record terminated by ``\\x01``.
        changed_files: Mapping of full SHA to changed file paths, used to attach
            the file list to the commit without an extra git call per commit.

    Returns:
        A populated :class:`GitCommit`, or ``None`` if the record is empty or
        malformed (e.g. the trailing empty record after the last separator).
    """
    fields = record.split(_FIELD_SEP, maxsplit=10)
    if len(fields) < 11:
        return None

    (
        sha,
        author_email,
        author_name,
        author_date_str,
        committer_email,
        committer_name,
        committer_date_str,
        subject,
        body,
        parents_str,
        raw_trailers,
    ) = fields

    sha = sha.strip()
    if not sha:
        return None

    body = body.rstrip("\n")
    trailers = _parse_trailers(raw_trailers)
    description = _strip_trailer_block(body) if trailers else body.strip()
    parent_shas = parents_str.strip().split() if parents_str.strip() else []

    return GitCommit(
        sha=sha,
        subject=subject,
        body=body,
        description=description,
        trailers=trailers,
        parent_shas=parent_shas,
        changed_files=changed_files.get(sha, []),
        author_name=author_name,
        author_email=author_email,
        author_date=datetime.fromisoformat(author_date_str),
        committer_name=committer_name,
        committer_email=committer_email,
        committer_date=datetime.fromisoformat(committer_date_str),
    )


def _get_changed_files(repo_path: Path, revision_range: str) -> dict[str, list[str]]:
    """Return a mapping of commit SHA → list of changed file paths for *revision_range*.

    Uses ``git log --name-only`` with a ``SHA:<hash>`` prefix marker so that
    file names that happen to be 40 hex characters long are never mistaken for
    commit hashes.

    Args:
        repo_path: Absolute path to the git repository root.
        revision_range: Git revision range, e.g. ``"main..HEAD"`` or ``"HEAD"``.

    Returns:
        Dict mapping full SHA strings to lists of changed file paths.
    """
    raw = _run_git(
        ["log", "--name-only", "--format=format:SHA:%H", revision_range], cwd=repo_path
    )

    files_by_sha: dict[str, list[str]] = {}
    current_sha: str | None = None

    for line in raw.splitlines():
        if line.startswith("SHA:"):
            current_sha = line[4:]
            files_by_sha[current_sha] = []
        elif line.strip() and current_sha is not None:
            files_by_sha[current_sha].append(line.strip())

    return files_by_sha


def _run_git(args: list[str], cwd: Path) -> str:
    """Run a git command and return its stdout as a string.

    Args:
        args: Arguments to pass to ``git``, excluding the ``git`` binary itself.
        cwd: Directory in which to run the command (must be inside a git repo).

    Returns:
        Raw stdout output of the command.

    Raises:
        subprocess.CalledProcessError: If git exits with a non-zero status.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def get_commits(
    repo_path: Path,
    base_ref: str | None = None,
    head_ref: str = "HEAD",
) -> list[GitCommit]:
    """Parse and return commits from a git repository.

    Args:
        repo_path: Path to the repository root.
        base_ref: Exclusive start of the commit range. When provided, only
            commits reachable from *head_ref* but not from *base_ref* are
            returned (i.e. the range ``base_ref..head_ref``). Typical CI usage:
            ``base_ref=$CI_MERGE_REQUEST_DIFF_BASE_SHA``. When ``None``, the
            single commit at *head_ref* is returned.
        head_ref: Inclusive end of the range. Defaults to ``"HEAD"``.

    Returns:
        List of :class:`~git_commit_analyzer.models.GitCommit` objects ordered
        from newest to oldest, matching ``git log`` output order.

    Raises:
        subprocess.CalledProcessError: If git is not available or *repo_path* is
            not inside a git repository.
    """
    revision_range = f"{base_ref}..{head_ref}" if base_ref else head_ref
    raw = _run_git(["log", f"--format={_FORMAT}", revision_range], cwd=repo_path)
    changed_files = _get_changed_files(repo_path, revision_range)

    commits = []
    for record in raw.split(_RECORD_SEP):
        commit = _parse_record(record, changed_files)
        if commit is not None:
            commits.append(commit)

    return commits
