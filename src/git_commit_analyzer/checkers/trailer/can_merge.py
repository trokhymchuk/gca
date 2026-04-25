from dataclasses import dataclass, field

from ...models import GitCommit
from ..base import CheckResult, CommitChecker


# rules:
#   - name: no-duplicate-co-authors
#     checkers:
#       - type: trailer_can_merge
#         trailers: ["Co-authored-by", "Signed-off-by"]
@dataclass
class TrailerCanMergeChecker(CommitChecker):
    """Ensures that each listed trailer token appears at most once.

    Use this for trailers whose multiple occurrences could be compressed
    into a single line, enforcing that authors do that compression before
    pushing.

    Attributes:
        trailers: Trailer tokens for which at most one instance is allowed.
    """

    name = "trailer_can_merge"

    trailers: list[str] = field(default_factory=list)

    def __call__(self, commit: GitCommit) -> CheckResult:
        errors: list[str] = []

        for token in self.trailers:
            count = len(commit.trailer(token))
            if count > 1:
                errors.append(
                    f"Trailer '{token}' appears {count} times but must appear at most once"
                )

        if errors:
            return CheckResult.fail("; ".join(errors))
        return CheckResult.ok("All trailers appear at most once")
