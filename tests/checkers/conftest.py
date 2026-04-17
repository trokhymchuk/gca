from datetime import datetime, timezone
from typing import Protocol

import pytest

from git_commit_analyzer import GitCommit, Trailer

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


class MakeCommit(Protocol):
    def __call__(
        self,
        subject: str = ...,
        description: str = ...,
        trailers: list[Trailer] | None = ...,
        changed_files: list[str] | None = ...,
    ) -> GitCommit: ...


@pytest.fixture
def make_commit() -> MakeCommit:
    def _make(
        subject: str = "feat: subject",
        description: str = "",
        trailers: list[Trailer] | None = None,
        changed_files: list[str] | None = None,
    ) -> GitCommit:
        return GitCommit(
            sha="a" * 40,
            subject=subject,
            body="",
            description=description,
            trailers=trailers or [],
            parent_shas=[],
            changed_files=changed_files or [],
            author_name="Test",
            author_email="test@example.com",
            author_date=_NOW,
            committer_name="Test",
            committer_email="test@example.com",
            committer_date=_NOW,
        )

    return _make  # type: ignore[return-value]
