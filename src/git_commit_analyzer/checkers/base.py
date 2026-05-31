from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..models import GitCommit


@dataclass(frozen=True)
class CheckResult:
    """Immutable outcome of running a single checker against a commit.

    Attributes:
        passed: ``True`` when the commit satisfies the checker's rule.
        message: Human-readable description of the outcome — explains what
            passed or, when ``passed`` is ``False``, exactly what failed and why.
    """

    passed: bool
    message: str

    @staticmethod
    def ok(message: str = "ok") -> "CheckResult":
        """Create a passing result.

        Args:
            message: Optional description of what passed. Defaults to ``"ok"``.

        Returns:
            A :class:`CheckResult` with ``passed=True``.
        """
        return CheckResult(passed=True, message=message)

    @staticmethod
    def fail(message: str) -> "CheckResult":
        """Create a failing result.

        Args:
            message: Description of what failed and why.

        Returns:
            A :class:`CheckResult` with ``passed=False``.
        """
        return CheckResult(passed=False, message=message)


class CommitChecker(ABC):
    """Abstract base class for all commit checkers.

    Attributes:
        name: Unique string identifier used in YAML rulesets (``type:`` field).
            Must be set on every concrete subclass; duplicates raise
            :exc:`TypeError` at class-definition time.
        fail_message: Optional custom message appended to the checker's failure
            output, providing extra guidance to the user. Set from the optional
            ``fail_message:`` key in a checker's YAML spec; ``None`` when absent.
            Declared here (not as a dataclass field) so every checker inherits
            it without affecting subclass constructors.
        _registry: Class-level mapping of ``name → class``, populated
            automatically via :meth:`__init_subclass__`.
    """

    name: str
    fail_message: str | None = None
    _registry: dict[str, type] = {}

    def __init_subclass__(cls, **kwargs: object) -> None:
        """Register the subclass under its ``name`` and enforce uniqueness.

        Args:
            **kwargs: Forwarded to ``super().__init_subclass__``.

        Raises:
            TypeError: If another subclass with the same ``name`` has already
                been registered.
        """
        super().__init_subclass__(**kwargs)
        if "name" not in cls.__dict__:
            return
        name = cls.__dict__["name"]
        if not isinstance(name, str):
            # Property descriptors (e.g. NegatedChecker) define name dynamically;
            # they are not registered because their name is instance-specific.
            return
        if name in CommitChecker._registry:
            existing = CommitChecker._registry[name].__qualname__
            raise TypeError(f"Checker name {name!r} is already used by {existing}")
        CommitChecker._registry[name] = cls

    @abstractmethod
    def __call__(self, commit: GitCommit) -> CheckResult:
        """Evaluate the checker against a commit.

        Args:
            commit: The commit to validate.

        Returns:
            A :class:`CheckResult` describing whether the commit passed or failed.
        """
        ...


# Usage: add invert: true to any checker spec to negate it.
#
# rules:
#   - name: no-wip-commits
#     checkers:
#       - type: subject_matches_regex
#         pattern: "^WIP:"
#         invert: true
class NegatedChecker(CommitChecker):
    """Inverts another checker: passes when the inner checker fails, and vice versa.

    Useful for expressing "this condition must NOT hold", e.g. a commit must not
    modify a certain file, or the subject must not match a forbidden pattern.

    In YAML rulesets use ``invert: true`` on any checker spec instead of
    constructing this class directly::

        checkers:
          - type: file_modified
            files: ["secrets.env"]
            invert: true

    Attributes:
        checker: The inner checker whose result is inverted.
    """

    # name is a property — __init_subclass__ skips non-string names so this
    # class is intentionally absent from the registry.
    @property
    def name(self) -> str:
        """Dynamic name derived from the wrapped checker, e.g. ``not_file_modified``."""
        return f"not_{self.checker.name}"

    def __init__(self, checker: "CommitChecker") -> None:
        """
        Args:
            checker: The checker to invert.
        """
        self.checker = checker

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Return the inverted result of the wrapped checker.

        Args:
            commit: The commit to evaluate.

        Returns:
            Passing result when the inner checker fails; failing result (including
            the inner checker's message) when the inner checker passes.
        """
        result = self.checker(commit)
        if result.passed:
            return CheckResult.fail(f"not({self.checker.name}): {result.message}")
        return CheckResult.ok(f"not({self.checker.name}): condition was not met")

    def __repr__(self) -> str:
        return f"NegatedChecker(checker={self.checker!r})"
