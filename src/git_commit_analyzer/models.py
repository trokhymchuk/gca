from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Trailer:
    """A single git trailer line parsed from a commit message.

    Trailers follow the ``Token: value`` convention defined by
    ``git interpret-trailers`` and appear at the end of a commit body,
    separated from the rest of the message by a blank line.

    Attributes:
        token: The trailer key, e.g. ``"Signed-off-by"``.
        value: The trailer value, e.g. ``"Alice <alice@example.com>"``.
    """

    token: str
    value: str

    def __str__(self) -> str:
        """Return the trailer in canonical ``Token: value`` format."""
        return f"{self.token}: {self.value}"


@dataclass
class GitCommit:
    """All data associated with a single git commit.

    Attributes:
        sha: Full 40-character commit hash.
        subject: First line of the commit message.
        body: Raw commit body as returned by git, including the trailer block.
        description: Body with the trailing trailer block stripped.
        trailers: Parsed trailer lines extracted from the end of the body.
        parent_shas: SHA hashes of parent commits (more than one means a merge).
        changed_files: Paths of files touched by this commit relative to the repo root.
        author_name: Name of the commit author.
        author_email: Email address of the commit author.
        author_date: Timestamp when the author originally made the commit.
        committer_name: Name of the committer (may differ from author on rebased commits).
        committer_email: Email address of the committer.
        committer_date: Timestamp when the commit was applied to the current branch.
    """

    sha: str
    subject: str
    body: str
    description: str
    trailers: list[Trailer]
    parent_shas: list[str]
    changed_files: list[str]
    author_name: str
    author_email: str
    author_date: datetime
    committer_name: str
    committer_email: str
    committer_date: datetime

    @property
    def short_sha(self) -> str:
        """First 12 characters of the SHA, suitable for display."""
        return self.sha[:12]

    @property
    def is_fixup(self) -> bool:
        """True for ``fixup!`` commits created by ``git commit --fixup``."""
        return self.subject.startswith("fixup! ")

    @property
    def is_squash(self) -> bool:
        """True when the subject starts with ``squash! ``."""
        return self.subject.startswith("squash! ")

    @property
    def is_amend(self) -> bool:
        """True when the subject starts with ``amend! ``."""
        return self.subject.startswith("amend! ")

    @property
    def is_merge(self) -> bool:
        """True when the commit has more than one parent."""
        return len(self.parent_shas) > 1

    @property
    def is_revert(self) -> bool:
        """True when the subject matches the ``Revert "<subject>"`` pattern produced by ``git revert``."""
        return self.subject.startswith('Revert "') and self.subject.endswith('"')

    @property
    def is_regular(self) -> bool:
        """True when the commit is none of fixup, squash, amend, merge, or revert."""
        return not (
            self.is_fixup
            or self.is_squash
            or self.is_amend
            or self.is_merge
            or self.is_revert
        )

    def trailer(self, token: str) -> list[str]:
        """Return all values for a given trailer token (case-insensitive).

        Args:
            token: Trailer key to look up, e.g. ``"Fixes"`` or ``"signed-off-by"``.

        Returns:
            A list of values for every matching trailer. Empty list when the
            trailer is absent.
        """
        token_lower = token.lower()
        return [t.value for t in self.trailers if t.token.lower() == token_lower]

    def __str__(self) -> str:
        """Return a human-readable multi-line summary of all fields including computed properties."""
        trailers_str = (
            "\n    ".join(str(t) for t in self.trailers) if self.trailers else "(none)"
        )
        parents_str = ", ".join(self.parent_shas) if self.parent_shas else "(none)"
        files_str = (
            "\n    ".join(self.changed_files) if self.changed_files else "(none)"
        )
        return (
            f"sha:            {self.sha}\n"
            f"short_sha:      {self.short_sha}\n"
            f"subject:        {self.subject}\n"
            f"description:    {self.description!r}\n"
            f"body:           {self.body!r}\n"
            f"trailers:       {trailers_str}\n"
            f"parent_shas:    {parents_str}\n"
            f"changed_files:  {files_str}\n"
            f"author:         {self.author_name} <{self.author_email}>\n"
            f"author_date:    {self.author_date.isoformat()}\n"
            f"committer:      {self.committer_name} <{self.committer_email}>\n"
            f"committer_date: {self.committer_date.isoformat()}\n"
            f"is_fixup:       {self.is_fixup}\n"
            f"is_squash:      {self.is_squash}\n"
            f"is_amend:       {self.is_amend}\n"
            f"is_merge:       {self.is_merge}\n"
            f"is_revert:      {self.is_revert}"
        )
