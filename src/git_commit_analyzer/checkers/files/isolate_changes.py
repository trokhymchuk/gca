from __future__ import annotations

from dataclasses import dataclass, field

from ...models import GitCommit
from ..base import CheckResult, CommitChecker


# rules:
#   - name: path-isolation
#     checkers:
#       - type: isolate_changes
#         groups:
#           - [".gitlab-ci.yml", ".gitlab/"]        # CI config together
#           - [".gitlab/", "profiles/"]              # infra changes together
#           - [".gitlab/tests/cram/"]                # cram tests alone
#
#   # Effect:
#   #   modify only src/                     → PASS  (no group triggered)
#   #   modify .gitlab/ + .gitlab-ci.yml     → PASS  (best group 0)
#   #   modify .gitlab/ + profiles/          → PASS  (best group 1)
#   #   modify .gitlab-ci.yml + profiles/    → FAIL  (group 0 vs group 1)
#   #   modify src/ + .gitlab/               → FAIL  (src/ ungrouped)
#   #   modify .gitlab/tests/cram/ + abc/    → FAIL  (cram → group 2, abc/ → group 1)
@dataclass
class IsolateChangesChecker(CommitChecker):
    """Ensures that changes stay isolated within defined path groups.

    Each inner list defines a group of paths that belong together.
    When deciding which group a file belongs to, the **most specific**
    matching pattern (longest pattern string) wins across all groups.
    If multiple groups tie on specificity, the file is compatible with
    all of them.

    A commit passes if every changed file shares at least one common
    best-match group.  Files outside all groups are only allowed when
    no group is triggered; mixing them with grouped files always fails.

    This means a more specific subgroup (e.g. ``".gitlab/tests/cram/"``)
    takes precedence over a broader group (``".gitlab/"``), so touching
    cram tests locks you into the cram group even though ``.gitlab/``
    would also match.

    Path conventions:
      - Entries ending with ``/`` are directory prefixes (``"src/"``
        matches ``"src/main.py"``).
      - All other entries are exact file paths.

    Attributes:
        groups: List of path groups. Each group is a list of path patterns.
    """

    name = "isolate_changes"

    groups: list[list[str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.groups:
            raise ValueError("'groups' must contain at least one group")

    def _matches_path(self, filepath: str, pattern: str) -> bool:
        if pattern.endswith("/"):
            return filepath.startswith(pattern)
        return filepath == pattern

    def _best_match_length_in_group(self, filepath: str, group: list[str]) -> int:
        """Longest matching pattern length in *group* for *filepath*, or -1."""
        best = -1
        for pattern in group:
            if self._matches_path(filepath, pattern):
                best = max(best, len(pattern))
        return best

    def _best_groups_for_file(self, filepath: str) -> frozenset[int]:
        """Indices of groups whose best-match length for *filepath* is maximal.

        Returns an empty frozenset when no group matches the file.
        """
        lengths = [self._best_match_length_in_group(filepath, g) for g in self.groups]
        best_len = max(lengths)
        if best_len < 0:
            return frozenset()
        return frozenset(i for i, ln in enumerate(lengths) if ln == best_len)

    def __call__(self, commit: GitCommit) -> CheckResult:
        changed = list(commit.changed_files)
        if not changed:
            return CheckResult.ok("No files changed")

        file_best_groups: dict[str, frozenset[int]] = {
            f: self._best_groups_for_file(f) for f in changed
        }

        # No file belongs to any group → no isolation triggered
        if all(not gs for gs in file_best_groups.values()):
            return CheckResult.ok("Changed files do not belong to any isolation group")

        # Ungrouped files mixed with grouped ones
        ungrouped = sorted(f for f, gs in file_best_groups.items() if not gs)
        if ungrouped:
            return CheckResult.fail(
                "Changes violate isolation constraints — ungrouped files "
                "mixed with group members: " + ", ".join(repr(f) for f in ungrouped)
            )

        # Intersect all files' best-group sets — must share at least one group
        common: frozenset[int] = frozenset(range(len(self.groups)))
        for gs in file_best_groups.values():
            common &= gs

        if common:
            return CheckResult.ok(
                "All changed files are within a single isolation group"
            )

        # Build a readable error: show each file with its best-group indices
        file_info = ", ".join(
            f"{f!r}→group{'s' if len(gs) > 1 else ''} "
            f"{'+'.join(str(i) for i in sorted(gs))}"
            for f, gs in sorted(file_best_groups.items())
        )
        return CheckResult.fail(
            f"Changes violate isolation constraints — files span multiple "
            f"isolation groups: {file_info}"
        )
