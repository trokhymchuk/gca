from dataclasses import dataclass, field
from fnmatch import fnmatch

from ...models import GitCommit
from ..base import CommitFilter


# Example usage:
#
# rules:
#   # Apply subject-length check only to commits touching src/ or tests/
#   - name: src-subject-length
#     filters:
#       - type: paths_modified
#         any_of: ["src/", "tests/"]
#     checkers:
#       - type: subject_length
#         max: 72
#
#   # Every commit that touches src/ must also update tests/
#   - name: src-needs-test-change
#     filters:
#       - type: paths_modified
#         any_of: ["src/"]
#     checkers:
#       - type: paths_modified
#         required: ["tests/"]
#
#   # Migration commits must touch both the migration file and the schema
#   - name: migration-must-include-schema
#     filters:
#       - type: paths_modified
#         any_of: ["migrations/"]
#     checkers:
#       - type: paths_modified
#         all_of: ["migrations/", "schema.sql"]
@dataclass
class PathsModifiedFilter(CommitFilter):
    """Passes based on whether specified paths have been modified.

    Each entry in ``any_of`` or ``all_of`` can be:

    * An exact file path (e.g. ``"Makefile"``).
    * A directory prefix ending with ``/`` (e.g. ``"src/"``).
    * A glob pattern containing ``*``, ``?``, or ``[`` (e.g. ``"**/*.py"``).

    The filter passes when:

    * ``any_of`` — at least one listed path is among the changed files.
    * ``all_of`` — every listed path has at least one match among the changed files.
    * Both — both conditions must hold simultaneously.

    Attributes:
        any_of: Pass if any of these paths is modified.
        all_of: Pass if all of these paths are modified.
    """

    name = "paths_modified"

    any_of: list[str] = field(default_factory=list)
    all_of: list[str] = field(default_factory=list)

    def _matches(self, path_entry: str, changed_files: list[str]) -> bool:
        """Return True if *path_entry* matches at least one changed file."""
        if path_entry.endswith("/"):
            prefix = path_entry
            return any(f.startswith(prefix) for f in changed_files)
        if any(c in path_entry for c in ("*", "?", "[")):
            return any(fnmatch(f, path_entry) for f in changed_files)
        return path_entry in changed_files

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` when the commit satisfies the path conditions.

        Args:
            commit: Commit whose changed-file list is inspected.

        Returns:
            ``True`` when all configured conditions are met.
        """
        if not self.any_of and not self.all_of:
            return False

        changed = commit.changed_files

        if self.any_of and not any(self._matches(p, changed) for p in self.any_of):
            return False

        if self.all_of and not all(self._matches(p, changed) for p in self.all_of):
            return False

        return True

    def __repr__(self) -> str:
        parts = []
        if self.any_of:
            parts.append(f"any_of={self.any_of!r}")
        if self.all_of:
            parts.append(f"all_of={self.all_of!r}")
        return f"PathsModifiedFilter({', '.join(parts)})"
