"""Commit filters — predicates that decide whether a commit is in scope for checking.

A filter returns ``True`` when a commit should be checked and ``False`` when it
should be skipped.  Filters are composed inside a :class:`~git_commit_analyzer.rules.Rule`:
all filters in a rule must pass before any checker is applied to that commit.

Extending
---------
Subclass :class:`CommitFilter`, set a unique ``name`` class attribute, and
implement ``__call__``.  The registry enforces uniqueness at class-definition
time, so a duplicate ``name`` raises :exc:`TypeError` on import.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from fnmatch import fnmatch

from .models import GitCommit


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


# ---------------------------------------------------------------------------
# Inversion wrapper
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Commit property filters
# ---------------------------------------------------------------------------

class IsFixupFilter(CommitFilter):
    """Passes if the commit is a fixup, squash, or amend commit.

    Matches subjects starting with ``fixup! ``, ``squash! ``, or ``amend! ``
    as produced by ``git commit --fixup`` / ``--squash``.
    """

    name = "is_fixup"

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` if ``commit.is_fixup`` is ``True``.

        Args:
            commit: The commit to evaluate.

        Returns:
            ``True`` for fixup, squash, and amend commits.
        """
        return commit.is_fixup


class IsSquashFilter(CommitFilter):
    """Passes if the commit subject starts with ``squash! ``."""

    name = "is_squash"

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` if ``commit.is_squash`` is ``True``.

        Args:
            commit: The commit to evaluate.
        """
        return commit.is_squash


class IsAmendFilter(CommitFilter):
    """Passes if the commit subject starts with ``amend! ``."""

    name = "is_amend"

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` if ``commit.is_amend`` is ``True``.

        Args:
            commit: The commit to evaluate.
        """
        return commit.is_amend


class IsMergeFilter(CommitFilter):
    """Passes if the commit has more than one parent (i.e. is a merge commit)."""

    name = "is_merge"

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` if ``commit.is_merge`` is ``True``.

        Args:
            commit: The commit to evaluate.
        """
        return commit.is_merge


class IsRevertFilter(CommitFilter):
    """Passes if the commit is a revert created by ``git revert``.

    Matches the ``Revert "<subject>"`` subject pattern.
    """

    name = "is_revert"

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` if ``commit.is_revert`` is ``True``.

        Args:
            commit: The commit to evaluate.
        """
        return commit.is_revert


# ---------------------------------------------------------------------------
# Changed-files filters
# ---------------------------------------------------------------------------

@dataclass
class FileModifiedFilter(CommitFilter):
    """Passes if any of the given exact file paths appears in the commit's changed files.

    Attributes:
        files: List of file paths to match against (relative to the repo root).
            The filter passes when *at least one* path is present in
            ``commit.changed_files``.
    """

    name = "file_modified"

    files: list[str]

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` if any of *files* was modified in *commit*.

        Args:
            commit: Commit whose changed-file list is inspected.

        Returns:
            ``True`` when at least one entry in :attr:`files` appears in
            ``commit.changed_files``.
        """
        changed = set(commit.changed_files)
        return any(f in changed for f in self.files)

    def __repr__(self) -> str:
        return f"FileModifiedFilter(files={self.files!r})"


@dataclass
class DirectoryModifiedFilter(CommitFilter):
    """Passes if any changed file lives under one of the given directories.

    Matching is prefix-based: a file ``src/pkg/module.py`` matches the
    directory ``src`` as well as ``src/pkg``.  Trailing slashes in
    :attr:`directories` are normalised before comparison.

    Attributes:
        directories: List of directory paths (relative to the repo root).
            Trailing slashes are ignored.
    """

    name = "directory_modified"

    directories: list[str]

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` if any changed file is under one of :attr:`directories`.

        Args:
            commit: Commit whose changed-file list is inspected.

        Returns:
            ``True`` when at least one changed file has a path that starts with
            one of the normalised directory prefixes.
        """
        prefixes = [d.rstrip("/") + "/" for d in self.directories]
        return any(
            any(f.startswith(prefix) for prefix in prefixes)
            for f in commit.changed_files
        )

    def __repr__(self) -> str:
        return f"DirectoryModifiedFilter(directories={self.directories!r})"


@dataclass
class GlobModifiedFilter(CommitFilter):
    """Passes if any changed file matches any of the given glob patterns.

    Uses :func:`fnmatch.fnmatch` for pattern matching, which supports ``*``,
    ``?``, and ``[seq]`` wildcards.  ``**`` is also supported via fnmatch's
    standard behaviour.

    Attributes:
        patterns: List of glob patterns to match against changed file paths.
    """

    name = "glob_modified"

    patterns: list[str]

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` if any changed file matches any of :attr:`patterns`.

        Args:
            commit: Commit whose changed-file list is inspected.

        Returns:
            ``True`` when at least one changed file matches at least one pattern.
        """
        return any(
            any(fnmatch(f, pattern) for pattern in self.patterns)
            for f in commit.changed_files
        )

    def __repr__(self) -> str:
        return f"GlobModifiedFilter(patterns={self.patterns!r})"
