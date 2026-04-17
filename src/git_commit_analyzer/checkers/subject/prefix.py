from __future__ import annotations

from dataclasses import dataclass, field

from ..._prefix_utils import chain_matches, extract_prefixes
from ...models import GitCommit
from ..base import CheckResult, CommitChecker

_VALID_MODES = ("whitelist", "blacklist")


# rules:
#   - name: conventional-prefix
#     checkers:
#       - type: subject_prefix
#         require_prefix: true
#         conventional: true
#         whitelist: [["feat"], ["fix"], ["chore"], ["docs"], ["style"],
#                     ["refactor"], ["test"], ["ci"]]
#
#   - name: no-wip-prefix
#     checkers:
#       - type: subject_prefix
#         blacklist: [["WIP"], ["DRAFT"]]
#
#   # Allow single 'feat:' or the chained 'ci: cram:' prefix
#   - name: allowed-prefixes
#     checkers:
#       - type: subject_prefix
#         whitelist: [["feat"], ["fix"], ["ci", "cram"]]
#
#   # ci: cram: commits must have both 'ci' and 'cram' tokens in the prefix chain
#   - name: cram-prefix-required
#     checkers:
#       - type: subject_prefix
#         required: [["ci"], ["cram"]]
@dataclass
class SubjectPrefixChecker(CommitChecker):
    """Validates the prefix chain of the commit subject line.

    A subject may carry multiple chained prefixes, e.g. ``ci: cram: add test``.
    The extracted chain (e.g. ``["ci", "cram"]``) is compared against each
    pattern (inner list) in ``whitelist`` / ``blacklist`` using exact,
    case-insensitive equality.

    The prefix format per segment is:
      - Non-conventional (default): ``prefix: ``
      - Conventional (``conventional=True``): ``prefix(scope): ``

    Attributes:
        require_prefix: When ``True`` (default), fails if no prefix is found.
        conventional: When ``True``, each prefix segment must follow the
            conventional commits format ``prefix(scope): …``.
        required: List of chain patterns; the commit's prefix chain must match
            **at least one** of them.  Each inner list is matched as a
            contiguous subsequence of the chain (case-insensitive).
            ``[["ci"], ["cram"]]`` passes if the chain contains ``ci`` OR
            ``cram`` (or both).
            ``[["ci", "cram"]]`` passes only if the chain contains the
            sub-sequence ``ci: cram:`` (e.g. ``ci: cram: add test``).
        whitelist: List of allowed prefix chains. Each inner list is one
            valid chain (e.g. ``[["feat"], ["ci", "cram"]]`` allows
            ``feat: …`` or ``ci: cram: …``). Effective only in
            ``"whitelist"`` mode.
        blacklist: List of forbidden prefix chains. Each inner list is one
            forbidden chain. Always enforced regardless of mode.
        mode: ``"whitelist"`` — chain must appear in ``whitelist``.
            ``"blacklist"`` — chain must not appear in ``blacklist``.
            Defaults to ``"whitelist"`` when only ``whitelist`` is provided,
            ``"blacklist"`` otherwise (including when neither list is set,
            meaning any prefix is allowed). Must be set explicitly when both
            are provided.
    """

    name = "subject_prefix"

    require_prefix: bool = True
    conventional: bool = False
    required: list[list[str]] = field(default_factory=list)
    whitelist: list[list[str]] = field(default_factory=list)
    blacklist: list[list[str]] = field(default_factory=list)
    mode: str | None = None

    def __post_init__(self) -> None:
        if self.whitelist and self.blacklist and self.mode is None:
            raise ValueError(
                "'mode' must be set explicitly when both 'whitelist' and "
                "'blacklist' are provided"
            )
        if self.mode is not None and self.mode not in _VALID_MODES:
            raise ValueError(f"'mode' must be one of {_VALID_MODES}, got '{self.mode}'")

    def _effective_mode(self) -> str:
        if self.mode is not None:
            return self.mode
        if self.whitelist and not self.blacklist:
            return "whitelist"
        return "blacklist"

    def _pattern_in_chain(self, chain: list[str], pattern: list[str]) -> bool:
        """Return True if *pattern* appears as a contiguous subsequence in *chain*."""
        n, m = len(chain), len(pattern)
        if m > n:
            return False
        return any(
            all(chain[i + j].lower() == pattern[j].lower() for j in range(m))
            for i in range(n - m + 1)
        )

    def _check_required(self, chain: list[str]) -> list[str]:
        """Return error messages when no pattern in ``required`` matches."""
        if not self.required:
            return []
        if any(self._pattern_in_chain(chain, pat) for pat in self.required):
            return []
        options = " | ".join(": ".join(p) + ":" for p in self.required)
        return [f"Prefix chain does not match any required pattern: [{options}]"]

    def __call__(self, commit: GitCommit) -> CheckResult:
        chain = extract_prefixes(commit.subject, conventional=self.conventional)

        if not chain:
            if self.require_prefix or self.required:
                fmt = "prefix(scope): …" if self.conventional else "prefix: …"
                hints: list[str] = []
                if self.required:
                    hints.extend(": ".join(p) + ":" for p in self.required)
                if self.whitelist and self._effective_mode() == "whitelist":
                    hints.extend(": ".join(p) + ":" for p in self.whitelist)
                hint_str = f"; expected one of: {hints}" if hints else ""
                return CheckResult.fail(
                    f"Subject has no valid prefix (expected format: {fmt!r}){hint_str}"
                )
            return CheckResult.ok("No prefix required and none found")

        effective_mode = self._effective_mode()
        errors: list[str] = []
        chain_str = ": ".join(chain) + ":"

        errors.extend(self._check_required(chain))

        if self.blacklist and any(chain_matches(chain, p) for p in self.blacklist):
            errors.append(f"Prefix chain '{chain_str}' is blacklisted")

        if (
            effective_mode == "whitelist"
            and self.whitelist
            and not any(chain_matches(chain, p) for p in self.whitelist)
        ):
            allowed = ", ".join("'" + ": ".join(p) + ":'" for p in self.whitelist)
            errors.append(
                f"Prefix chain '{chain_str}' is not in the whitelist; "
                f"allowed: [{allowed}]"
            )

        if errors:
            return CheckResult.fail("; ".join(errors))
        return CheckResult.ok(f"Subject prefix chain '{chain_str}' is valid")
