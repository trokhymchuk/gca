from dataclasses import dataclass, field

from ...models import GitCommit
from ..base import CheckResult, CommitChecker


# rules:
#   - name: subject-length
#     checkers:
#       - type: subject_length
#         min: 10
#         max: 72
@dataclass
class SubjectLengthChecker(CommitChecker):
    """Validates subject length against optional minimum and maximum bounds.

    At least one of ``min`` or ``max`` should be specified, otherwise the
    checker always passes.

    Attributes:
        min: Minimum number of characters required in the subject. ``None``
            disables the minimum check.
        max: Maximum number of characters allowed in the subject. ``None``
            disables the maximum check.
    """

    name = "subject_length"

    min: int | None = field(default=None)
    max: int | None = field(default=None)

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check subject length against configured bounds.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result if subject length is within bounds.
            Failing result describing the violation.
        """
        length = len(commit.subject)
        errors: list[str] = []

        if self.min is not None and length < self.min:
            errors.append(
                f"Subject is {length} characters, below minimum of {self.min}"
            )

        if self.max is not None and length > self.max:
            errors.append(
                f"Subject is {length} characters, exceeds maximum of {self.max}"
            )

        if errors:
            return CheckResult.fail("; ".join(errors))
        return CheckResult.ok(f"Subject length {length} is within bounds")
