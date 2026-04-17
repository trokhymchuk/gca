from dataclasses import dataclass, field

from ...models import GitCommit
from ..base import CheckResult, CommitChecker


# rules:
#   - name: src-changes-need-description
#     checkers:
#       - type: description_length
#         min: 20
#         line_max: 100
@dataclass
class DescriptionLengthChecker(CommitChecker):
    """Validates description length against optional total minimum and per-line maximum.

    At least one of ``min`` or ``line_max`` should be specified, otherwise the
    checker always passes.

    Attributes:
        min: Minimum total number of characters required in the description.
            ``None`` disables the minimum check.
        line_max: Maximum number of characters allowed per individual line.
            ``None`` disables the per-line check.
    """

    name = "description_length"

    min: int | None = field(default=None)
    line_max: int | None = field(default=None)

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check description length against configured bounds.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result if description satisfies all length constraints.
            Failing result describing the first violation found.
        """
        errors: list[str] = []

        if self.min is not None:
            length = len(commit.description)
            if length < self.min:
                errors.append(
                    f"Description is {length} characters, below minimum of {self.min}"
                )

        if self.line_max is not None:
            for i, line in enumerate(commit.description.splitlines(), start=1):
                if len(line) > self.line_max:
                    errors.append(
                        f"Line {i} is {len(line)} characters, exceeds maximum of "
                        f"{self.line_max}: {line!r}"
                    )
                    break

        if errors:
            return CheckResult.fail("; ".join(errors))
        return CheckResult.ok("Description length is within bounds")
