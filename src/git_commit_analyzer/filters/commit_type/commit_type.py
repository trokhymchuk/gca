from dataclasses import dataclass

from ...models import GitCommit
from ..base import CommitFilter

_VALID_TYPES = frozenset({"fixup", "squash", "amend", "merge", "revert", "regular"})


# Example usage:
#
# rules:
#   # Skip all merge commits from subject-length enforcement
#   - name: subject-length
#     filters:
#       - type: commit_type
#         types: ["merge"]
#         invert: true
#     checkers:
#       - type: subject_length
#         max: 72
#
#   # Apply conventional-commit rules only to regular (non-fixup/merge/revert) commits
#   - name: conventional-commits
#     filters:
#       - type: commit_type
#         types: ["regular"]
#     checkers:
#       - type: subject_matches_regex
#         pattern: "^(feat|fix|chore|docs|refactor|test|style|perf)(\\(.+\\))?: .+"
#
#   # Revert commits must include a description explaining why
#   - name: revert-needs-description
#     filters:
#       - type: commit_type
#         types: ["revert"]
#     checkers:
#       - type: description_length
#         min: 20
@dataclass
class CommitTypeFilter(CommitFilter):
    """Passes if the commit matches any of the listed commit types.

    Supported types: ``fixup``, ``squash``, ``amend``, ``merge``, ``revert``, ``regular``.

    - ``fixup``: subject starts with ``fixup! ``
    - ``squash``: subject starts with ``squash! ``
    - ``amend``: subject starts with ``amend! ``
    - ``merge``: commit has 2+ parents
    - ``revert``: subject matches ``Revert "..."``
    - ``regular``: none of the above

    Attributes:
        types: List of commit type names to match against.
    """

    name = "commit_type"

    types: list[str]

    def __post_init__(self) -> None:
        """Validate that all type names are recognized."""
        invalid = [t for t in self.types if t not in _VALID_TYPES]
        if invalid:
            raise ValueError(
                f"Unknown commit type(s): {invalid}. "
                f"Valid types: {sorted(_VALID_TYPES)}"
            )

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` if the commit matches any of :attr:`types`.

        Args:
            commit: The commit to evaluate.

        Returns:
            ``True`` when the commit is any of the listed types.
        """
        for t in self.types:
            if t == "fixup" and commit.is_fixup:
                return True
            if t == "squash" and commit.is_squash:
                return True
            if t == "amend" and commit.is_amend:
                return True
            if t == "merge" and commit.is_merge:
                return True
            if t == "revert" and commit.is_revert:
                return True
            if t == "regular" and commit.is_regular:
                return True
        return False

    def __repr__(self) -> str:
        return f"CommitTypeFilter(types={self.types!r})"
