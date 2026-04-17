import re
from dataclasses import dataclass

from ...models import GitCommit
from ..base import CheckResult, CommitChecker


# rules:
#   - name: conventional-commits
#     checkers:
#       - type: subject_matches_regex
#         pattern: "^(feat|fix|chore|docs|style|refactor|test|ci)(\\(.+\\))?: .+"
@dataclass
class SubjectMatchesRegexChecker(CommitChecker):
    """Fails if the commit subject does not match the given regex pattern.

    Attributes:
        pattern: Regular expression tested against the full subject string
            using :func:`re.search` (anchoring with ``^``/``$`` is optional).
    """

    name = "subject_matches_regex"

    pattern: str

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that the subject matches :attr:`pattern`.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result on a match; failing result including the subject
            text and the pattern on a non-match.
        """
        if re.search(self.pattern, commit.subject):
            return CheckResult.ok(f"Subject matches pattern '{self.pattern}'")
        return CheckResult.fail(
            f"Subject {commit.subject!r} does not match pattern '{self.pattern}'"
        )
