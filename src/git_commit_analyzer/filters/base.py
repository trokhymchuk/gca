from abc import ABC, abstractmethod

from ..models import GitCommit


class CommitFilter(ABC):
    """Abstract base class for all commit filters.

    Attributes:
        name: Unique string identifier used in YAML rulesets (``type:`` field).
            Must be set on every concrete subclass; duplicates raise
            :exc:`TypeError` at class-definition time.
        _registry: Class-level mapping of ``name → class``, populated
            automatically via :meth:`__init_subclass__`.
    """

    name: str
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
            # Property descriptors (e.g. NegatedFilter) define name dynamically;
            # they are not registered because their name is instance-specific.
            return
        if name in CommitFilter._registry:
            existing = CommitFilter._registry[name].__qualname__
            raise TypeError(f"Filter name {name!r} is already used by {existing}")
        CommitFilter._registry[name] = cls

    @abstractmethod
    def __call__(self, commit: GitCommit) -> bool:
        """Evaluate the filter against a commit.

        Args:
            commit: The commit to evaluate.

        Returns:
            ``True`` if the commit is in scope (should be checked),
            ``False`` if it should be skipped.
        """
        ...

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


# Usage: add invert: true to any filter spec to negate it.
#
# rules:
#   - name: conventional-commits-non-merge
#     filters:
#       - type: is_merge
#         invert: true
#     checkers:
#       - type: subject_matches_regex
#         pattern: "^(feat|fix|chore): .+"
class NegatedFilter(CommitFilter):
    """Inverts another filter: passes when the inner filter fails, and vice versa.

    Useful for excluding specific commit types from a rule, e.g. skipping merge
    commits or applying a rule only to non-fixup commits.

    In YAML rulesets use ``invert: true`` on any filter spec instead of
    constructing this class directly::

        filters:
          - type: is_merge
            invert: true   # skip merge commits

    Attributes:
        inner: The filter whose result is inverted.
    """

    # name is a property — __init_subclass__ skips non-string names so this
    # class is intentionally absent from the registry.
    @property
    def name(self) -> str:
        """Dynamic name derived from the wrapped filter, e.g. ``not_is_merge``."""
        return f"not_{self.inner.name}"

    def __init__(self, inner: "CommitFilter") -> None:
        """
        Args:
            inner: The filter to invert.
        """
        self.inner = inner

    def __call__(self, commit: GitCommit) -> bool:
        """Return the inverted result of the wrapped filter.

        Args:
            commit: The commit to evaluate.

        Returns:
            ``True`` when the inner filter returns ``False``, and vice versa.
        """
        return not self.inner(commit)

    def __repr__(self) -> str:
        return f"NegatedFilter(inner={self.inner!r})"
