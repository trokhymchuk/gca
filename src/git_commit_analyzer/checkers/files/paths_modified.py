from __future__ import annotations

from dataclasses import dataclass, field

from ...models import GitCommit
from ..base import CheckResult, CommitChecker

_VALID_MODES = ("whitelist", "blacklist")


# rules:
#   - name: migrations-must-be-isolated
#     checkers:
#       - type: paths_modified
#         whitelist: ["db/migrations/"]   # only migrations dir allowed
#
#   - name: no-secrets-in-commits
#     checkers:
#       - type: paths_modified
#         blacklist: [".env", "secrets/"]  # these must never be modified
#
#   - name: db-commits-must-touch-migration
#     checkers:
#       - type: paths_modified
#         required: ["db/migrations/"]    # must touch migrations
#         whitelist: ["db/migrations/", "src/models.py"]
#         blacklist: [".env"]
#         mode: blacklist   # required when both whitelist and blacklist are set
@dataclass
class PathsModifiedChecker(CommitChecker):
    """Validates which paths were modified using whitelist/blacklist rules.

    Path conventions:
      - Entries ending with ``/`` are directory prefixes (e.g. ``"src/"``
        matches ``"src/main.py"``).
      - All other entries are exact file paths.

    Attributes:
        required: Paths that must appear in the commit's changed files.
        whitelist: If set and effective mode is ``"blacklist"``, every changed
            file must match at least one of these paths.
        blacklist: Changed files matching any of these paths always fail,
            regardless of mode.
        mode: Controls treatment of files not explicitly listed.
            Defaults to ``"blacklist"`` when only ``whitelist`` is provided
            (files outside the whitelist are forbidden).
            Defaults to ``"whitelist"`` when only ``blacklist`` is provided
            (files outside the blacklist are allowed).
            Must be set explicitly when both ``whitelist`` and ``blacklist``
            are provided.
    """

    name = "paths_modified"

    required: list[str] = field(default_factory=list)
    whitelist: list[str] = field(default_factory=list)
    blacklist: list[str] = field(default_factory=list)
    mode: str | None = None

    def __post_init__(self) -> None:
        if self.whitelist and self.blacklist and self.mode is None:
            raise ValueError(
                "'mode' must be set explicitly when both 'whitelist' and "
                "'blacklist' are provided"
            )
        if self.mode is not None and self.mode not in _VALID_MODES:
            raise ValueError(f"'mode' must be one of {_VALID_MODES}, got '{self.mode}'")

    def _effective_mode(self) -> str | None:
        if self.mode is not None:
            return self.mode
        if self.whitelist and not self.blacklist:
            return "whitelist"  # only whitelisted paths allowed
        if self.blacklist and not self.whitelist:
            return "blacklist"  # only blacklisted paths are forbidden
        return None

    def _matches_path(self, filepath: str, pattern: str) -> bool:
        if pattern.endswith("/"):
            return filepath.startswith(pattern)
        return filepath == pattern

    def _matches_any(self, filepath: str, patterns: list[str]) -> bool:
        return any(self._matches_path(filepath, p) for p in patterns)

    def __call__(self, commit: GitCommit) -> CheckResult:
        errors: list[str] = []
        effective_mode = self._effective_mode()

        # required: each path must appear in changed files
        for path in self.required:
            if not any(self._matches_path(f, path) for f in commit.changed_files):
                errors.append(f"Required path '{path}' was not modified")

        for filepath in commit.changed_files:
            in_blacklist = (
                self._matches_any(filepath, self.blacklist) if self.blacklist else False
            )
            in_whitelist = (
                self._matches_any(filepath, self.whitelist) if self.whitelist else False
            )

            if in_blacklist:
                errors.append(f"Prohibited path modified: '{filepath}'")
            elif effective_mode == "whitelist" and self.whitelist and not in_whitelist:
                errors.append(f"Path '{filepath}' is not in the whitelist")

        if errors:
            return CheckResult.fail("; ".join(errors))
        return CheckResult.ok("All path modification rules satisfied")
