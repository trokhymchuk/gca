import re
from dataclasses import dataclass

from ...models import GitCommit
from ..base import CheckResult, CommitChecker


# rules:
#   - name: docs-must-reference-section
#     checkers:
#       - type: description_matches_regex
#         pattern: "(?i)section|chapter|page|readme"
@dataclass
class DescriptionMatchesRegexChecker(CommitChecker):
    """Fails if the commit description does not match the given regex pattern.

    Attributes:
        pattern: Regular expression tested against the full description string
            using :func:`re.search`.
    """

    name = "description_matches_regex"

    pattern: str

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that the description matches :attr:`pattern`.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result on a match; failing result including the pattern
            on a non-match.
        """
        if re.search(self.pattern, commit.description):
            return CheckResult.ok(f"Description matches pattern '{self.pattern}'")
        return CheckResult.fail(f"Description does not match pattern '{self.pattern}'")
