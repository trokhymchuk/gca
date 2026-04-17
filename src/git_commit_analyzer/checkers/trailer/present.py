from dataclasses import dataclass, field

from ...models import GitCommit
from ..base import CheckResult, CommitChecker

_VALID_MODES = ("whitelist", "blacklist")


# rules:
#   - name: require-sign-off-and-ticket
#     checkers:
#       - type: trailer_present
#         required: ["Signed-off-by"]
#         at_least_one_of:
#           - ["Fixes", "Closes", "Refs"]
#         exactly_one_of:
#           - ["Co-authored-by", "Reviewed-by"]
#         whitelist: ["Change-Id"]
#         blacklist: ["WIP"]
#         mode: blacklist   # default; use whitelist to reject unlisted trailers
@dataclass
class TrailerPresentChecker(CommitChecker):
    """Validates trailer presence according to flexible rules.

    Attributes:
        required: Trailer tokens that must all be present with non-empty values.
        at_least_one_of: Each inner list is a group; for every group at least
            one token must be present with a non-empty value.
        exactly_one_of: Each inner list is a group; for every group exactly
            one token must be present (having multiple tokens from the same
            group is an error).
        whitelist: Additional trailer tokens that are explicitly permitted.
            In ``whitelist`` mode these are the only extras beyond ``required``,
            ``at_least_one_of`` and ``exactly_one_of`` that are allowed.
        blacklist: Trailer tokens that must not be present at all.
        mode: ``"blacklist"`` (default) — unlisted trailers are allowed; only
            tokens in ``blacklist`` are rejected.  ``"whitelist"`` — only tokens
            in ``required``, ``at_least_one_of``, ``exactly_one_of``, and
            ``whitelist`` are permitted; any other token causes a failure.
    """

    name = "trailer_present"

    required: list[str] = field(default_factory=list)
    at_least_one_of: list[list[str]] = field(default_factory=list)
    exactly_one_of: list[list[str]] = field(default_factory=list)
    whitelist: list[str] = field(default_factory=list)
    blacklist: list[str] = field(default_factory=list)
    mode: str = "blacklist"

    def __post_init__(self) -> None:
        if self.mode not in _VALID_MODES:
            raise ValueError(f"'mode' must be one of {_VALID_MODES}, got '{self.mode}'")

    def _has_non_empty(self, commit: GitCommit, token: str) -> bool:
        return any(v.strip() for v in commit.trailer(token))

    def _is_present(self, commit: GitCommit, token: str) -> bool:
        return len(commit.trailer(token)) > 0

    def __call__(self, commit: GitCommit) -> CheckResult:
        errors: list[str] = []

        # required: all must be present with non-empty values
        for token in self.required:
            if not self._has_non_empty(commit, token):
                if self._is_present(commit, token):
                    errors.append(f"Trailer '{token}' is present but empty")
                else:
                    errors.append(f"Required trailer '{token}' is missing")

        # at_least_one_of: at least one per group must be present
        for group in self.at_least_one_of:
            present = [t for t in group if self._has_non_empty(commit, t)]
            if not present:
                empty = [t for t in group if self._is_present(commit, t)]
                if empty:
                    quoted = ", ".join(f"'{t}'" for t in empty)
                    errors.append(f"Trailer(s) {quoted} present but empty")
                else:
                    quoted = ", ".join(f"'{t}'" for t in group)
                    errors.append(f"At least one of [{quoted}] must be present")

        # exactly_one_of: exactly one per group must be present
        for group in self.exactly_one_of:
            present = [t for t in group if self._has_non_empty(commit, t)]
            if len(present) == 0:
                quoted = ", ".join(f"'{t}'" for t in group)
                errors.append(f"Exactly one of [{quoted}] must be present")
            elif len(present) > 1:
                quoted = ", ".join(f"'{t}'" for t in present)
                errors.append(
                    f"Only one of [{quoted}] may be present, but found multiple"
                )

        # blacklist: none of these may appear
        if self.blacklist:
            blacklist_lower = {t.lower() for t in self.blacklist}
            forbidden = [
                tr.token
                for tr in commit.trailers
                if tr.token.lower() in blacklist_lower
            ]
            if forbidden:
                unique = list(dict.fromkeys(forbidden))
                errors.append(f"Forbidden trailer(s): {', '.join(unique)}")

        # whitelist mode: reject trailers not in the known sets
        if self.mode == "whitelist":
            allowed: set[str] = set()
            for t in self.required:
                allowed.add(t.lower())
            for group in self.at_least_one_of:
                for t in group:
                    allowed.add(t.lower())
            for group in self.exactly_one_of:
                for t in group:
                    allowed.add(t.lower())
            for t in self.whitelist:
                allowed.add(t.lower())

            unlisted = [
                tr.token for tr in commit.trailers if tr.token.lower() not in allowed
            ]
            if unlisted:
                unique = list(dict.fromkeys(unlisted))
                errors.append(
                    f"Unlisted trailer(s) not allowed in whitelist mode: "
                    f"{', '.join(unique)}"
                )

        if errors:
            return CheckResult.fail("; ".join(errors))
        return CheckResult.ok("All trailer rules satisfied")
