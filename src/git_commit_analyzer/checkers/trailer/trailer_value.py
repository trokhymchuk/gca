import re
from dataclasses import dataclass, field

from ...models import GitCommit
from ..base import CheckResult, CommitChecker

_VALID_MODES = ("whitelist", "blacklist")


# Example usage:
#
# rules:
#   # Neither WIP nor Skip-CI may be set to "true"
#   - name: no-wip-trailers
#     checkers:
#       - type: trailer_value
#         trailers: [WIP, Skip-CI]
#         mode: blacklist
#         literals: ["true", "yes"]
#
#   # Both Fixes and Closes must reference a JIRA ticket
#   - name: fixes-must-be-jira
#     checkers:
#       - type: trailer_value
#         trailers: [Fixes, Closes]
#         mode: whitelist
#         regexps: ["^JIRA-\\d+$"]
#
#   # Signed-off-by must not be a bot account
#   - name: no-bot-sign-offs
#     checkers:
#       - type: trailer_value
#         trailers: [Signed-off-by]
#         mode: blacklist
#         regexps: ["bot@example\\.com"]
@dataclass
class TrailerValueChecker(CommitChecker):
    """Validates the values of one or more git trailers.

    A trailer value "matches" if it equals any entry in ``literals`` or is
    found by any pattern in ``regexps`` (via ``re.search``).  Every trailer
    listed in ``trailers`` is checked independently; all must pass.

    Both modes pass when a listed trailer is absent — they constrain values,
    not presence.  In ``whitelist`` mode the listed literals/regexps are the
    *only* values allowed: a present trailer fails if none of its values
    match.  In ``blacklist`` mode the listed literals/regexps are forbidden:
    a present trailer fails if any of its values match.

    Attributes:
        trailers: Trailer tokens to inspect.  Token matching is
            case-insensitive, following ``git interpret-trailers`` conventions.
        mode: ``"whitelist"`` — when present, every value must match an allowed
            literal/regexp.  ``"blacklist"`` — no value may match a forbidden
            literal/regexp.  Both pass when the trailer is absent.
        literals: Exact string values to compare against (case-sensitive).
        regexps: Regular expression patterns evaluated with ``re.search``
            against each trailer value.
    """

    name = "trailer_value"

    trailers: list[str]
    mode: str
    literals: list[str] = field(default_factory=list)
    regexps: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.mode not in _VALID_MODES:
            raise ValueError(f"'mode' must be one of {_VALID_MODES}, got '{self.mode}'")
        if not self.literals and not self.regexps:
            raise ValueError("At least one of 'literals' or 'regexps' must be provided")

    def _value_matches(self, value: str) -> bool:
        if value in self.literals:
            return True
        return any(re.search(pat, value) is not None for pat in self.regexps)

    def _check_one(self, commit: GitCommit, token: str) -> str | None:
        """Return an error string for *token*, or ``None`` if it passes."""
        values = commit.trailer(token)

        if self.mode == "whitelist":
            if not values:
                return None
            matching = [v for v in values if self._value_matches(v)]
            if not matching:
                return (
                    f"Trailer '{token}' value(s) {values!r} do not match "
                    f"the allowed literals/regexps"
                )
            return None

        # blacklist
        matching = [v for v in values if self._value_matches(v)]
        if matching:
            return f"Trailer '{token}' has forbidden value(s): {matching!r}"
        return None

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Evaluate every listed trailer against the configured mode.

        Args:
            commit: Commit whose trailers are inspected.

        Returns:
            A :class:`CheckResult` describing whether the commit passed or failed.
        """
        errors = [e for token in self.trailers if (e := self._check_one(commit, token))]
        if errors:
            return CheckResult.fail("; ".join(errors))
        return CheckResult.ok("All trailer value checks passed")

    def __repr__(self) -> str:
        parts = [f"trailers={self.trailers!r}", f"mode={self.mode!r}"]
        if self.literals:
            parts.append(f"literals={self.literals!r}")
        if self.regexps:
            parts.append(f"regexps={self.regexps!r}")
        return f"TrailerValueChecker({', '.join(parts)})"
