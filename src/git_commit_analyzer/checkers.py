"""Commit checkers — validators that inspect a single commit and report pass/fail.

Each checker receives a :class:`~git_commit_analyzer.models.GitCommit` and
returns a :class:`CheckResult` describing whether the commit satisfies a
particular guideline.

Extending
---------
Subclass :class:`CommitChecker`, set a unique ``name`` class attribute, and
implement ``__call__``.  The registry enforces uniqueness at class-definition
time, so a duplicate ``name`` raises :exc:`TypeError` on import.
"""

import re
import sys
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from .models import GitCommit


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


# ---------------------------------------------------------------------------
# Inversion wrapper
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Trailer checkers
# ---------------------------------------------------------------------------

@dataclass
class TrailerPresentChecker(CommitChecker):
    """Fails if the required trailer token is absent or has an empty value.

    Attributes:
        token: Trailer key to require, e.g. ``"Signed-off-by"``.
            Matching is case-insensitive.
    """

    name = "trailer_present"

    token: str

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that *token* is present with a non-empty value.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result if the trailer exists and has a non-whitespace value.
            Failing result if the trailer is missing or its value is blank.
        """
        values = [v for v in commit.trailer(self.token) if v.strip()]
        if values:
            return CheckResult.ok(f"Trailer '{self.token}' is present")
        if commit.trailer(self.token):
            return CheckResult.fail(f"Trailer '{self.token}' is present but empty")
        return CheckResult.fail(f"Required trailer '{self.token}' is missing")


@dataclass
class AnyTrailerPresentChecker(CommitChecker):
    """Fails if none of the given trailer tokens are present with a non-empty value.

    Attributes:
        tokens: List of trailer keys, any one of which satisfies the check.
            Matching is case-insensitive.
    """

    name = "any_trailer_present"

    tokens: list[str]

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that at least one token from :attr:`tokens` has a non-empty value.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result if at least one token is present with a non-blank value.
            Failing result with a specific message distinguishing between
            "all tokens missing" and "tokens present but empty".
        """
        present = [t for t in self.tokens if any(v.strip() for v in commit.trailer(t))]
        if present:
            return CheckResult.ok(f"Trailer(s) present: {', '.join(present)}")
        empty = [t for t in self.tokens if commit.trailer(t)]
        if empty:
            quoted = ", ".join(f"'{t}'" for t in empty)
            return CheckResult.fail(f"Trailer(s) {quoted} present but empty")
        quoted = ", ".join(f"'{t}'" for t in self.tokens)
        return CheckResult.fail(f"At least one of [{quoted}] must be present")


# ---------------------------------------------------------------------------
# Subject checkers
# ---------------------------------------------------------------------------

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


@dataclass
class SubjectMaxLengthChecker(CommitChecker):
    """Fails if the subject exceeds a maximum character count.

    Attributes:
        max_length: Maximum number of characters allowed in the subject line.
    """

    name = "subject_max_length"

    max_length: int

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that the subject is no longer than :attr:`max_length` characters.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result if ``len(subject) <= max_length``; failing result
            reporting the actual and maximum lengths otherwise.
        """
        length = len(commit.subject)
        if length <= self.max_length:
            return CheckResult.ok(f"Subject length {length} ≤ {self.max_length}")
        return CheckResult.fail(
            f"Subject is {length} characters, exceeds maximum of {self.max_length}"
        )


@dataclass
class SubjectMinLengthChecker(CommitChecker):
    """Fails if the subject is shorter than a minimum character count.

    Attributes:
        min_length: Minimum number of characters required in the subject line.
    """

    name = "subject_min_length"

    min_length: int

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that the subject is at least :attr:`min_length` characters long.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result if ``len(subject) >= min_length``; failing result
            reporting the actual and minimum lengths otherwise.
        """
        length = len(commit.subject)
        if length >= self.min_length:
            return CheckResult.ok(f"Subject length {length} ≥ {self.min_length}")
        return CheckResult.fail(
            f"Subject is {length} characters, below minimum of {self.min_length}"
        )


# ---------------------------------------------------------------------------
# Description checkers
# ---------------------------------------------------------------------------

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
        return CheckResult.fail(
            f"Description does not match pattern '{self.pattern}'"
        )


@dataclass
class DescriptionMinLengthChecker(CommitChecker):
    """Fails if the description is shorter than a minimum character count.

    Attributes:
        min_length: Minimum total number of characters required in the description.
    """

    name = "description_min_length"

    min_length: int

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that the description is at least :attr:`min_length` characters long.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result if ``len(description) >= min_length``; failing result
            reporting the actual and minimum lengths otherwise.
        """
        length = len(commit.description)
        if length >= self.min_length:
            return CheckResult.ok(f"Description length {length} ≥ {self.min_length}")
        return CheckResult.fail(
            f"Description is {length} characters, below minimum of {self.min_length}"
        )


@dataclass
class DescriptionLineMaxLengthChecker(CommitChecker):
    """Fails if any individual line in the description exceeds a maximum character count.

    Attributes:
        max_length: Maximum number of characters allowed per line.
    """

    name = "description_line_max_length"

    max_length: int

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that every line in the description is within :attr:`max_length` characters.

        Stops at the first offending line and reports its 1-based line number,
        length, limit, and content.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result if all lines are within the limit, or the description
            is empty.  Failing result identifying the first line that exceeds it.
        """
        for i, line in enumerate(commit.description.splitlines(), start=1):
            if len(line) > self.max_length:
                return CheckResult.fail(
                    f"Line {i} is {len(line)} characters, exceeds maximum of {self.max_length}: {line!r}"
                )
        return CheckResult.ok(f"All description lines ≤ {self.max_length} characters")


# ---------------------------------------------------------------------------
# Changed files checkers
# ---------------------------------------------------------------------------

@dataclass
class OnlyFilesModifiedChecker(CommitChecker):
    """Fails if any changed file is not in the explicitly allowed list.

    Useful for commits that should be strictly scoped to a known set of files,
    such as generated files or lock files.

    Attributes:
        files: Exhaustive list of file paths that are permitted to be changed.
    """

    name = "only_files_modified"

    files: list[str]

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that every changed file is in :attr:`files`.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result if all changed files are in the allowed set.
            Failing result listing the unexpected files otherwise.
        """
        allowed = set(self.files)
        unexpected = [f for f in commit.changed_files if f not in allowed]
        if not unexpected:
            return CheckResult.ok("Only allowed files are modified")
        return CheckResult.fail(
            f"Unexpected file(s) modified: {', '.join(unexpected)}"
        )


@dataclass
class OnlyDirectoriesModifiedChecker(CommitChecker):
    """Fails if any changed file is outside the allowed directories.

    Useful for isolating commits to a specific area of the repository,
    such as requiring migration commits to only touch ``migrations/``.

    Attributes:
        directories: List of directory prefixes that changed files must be
            contained within.  Trailing slashes are normalised.
    """

    name = "only_directories_modified"

    directories: list[str]

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that every changed file is under one of :attr:`directories`.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result if all changed files are within the allowed directories.
            Failing result listing the out-of-scope files otherwise.
        """
        prefixes = [d.rstrip("/") + "/" for d in self.directories]
        unexpected = [
            f for f in commit.changed_files
            if not any(f.startswith(prefix) for prefix in prefixes)
        ]
        if not unexpected:
            return CheckResult.ok("All modified files are within allowed directories")
        return CheckResult.fail(
            f"File(s) modified outside allowed directories: {', '.join(unexpected)}"
        )


@dataclass
class FileModifiedChecker(CommitChecker):
    """Fails if none of the specified files appear in the commit's changed files.

    The inverse of :class:`OnlyFilesModifiedChecker`: this checker requires that
    at least one of the listed files was actually modified, rather than restricting
    which files may be modified.

    Attributes:
        files: List of file paths (relative to repo root).  At least one must
            appear in ``commit.changed_files`` for the check to pass.
    """

    name = "file_modified"

    files: list[str]

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that at least one file from :attr:`files` was modified.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result naming the matched file(s).  Failing result listing
            the required files when none were found.
        """
        changed = set(commit.changed_files)
        matched = [f for f in self.files if f in changed]
        if matched:
            return CheckResult.ok(f"Expected file(s) modified: {', '.join(matched)}")
        return CheckResult.fail(
            f"None of the expected file(s) were modified: {', '.join(self.files)}"
        )


@dataclass
class DirectoryModifiedChecker(CommitChecker):
    """Fails if no changed file lives under any of the specified directories.

    The inverse of :class:`OnlyDirectoriesModifiedChecker`: requires that at
    least one file within the given directories was modified.

    Attributes:
        directories: List of directory prefixes (relative to repo root).
            At least one changed file must fall under one of these.
            Trailing slashes are normalised.
    """

    name = "directory_modified"

    directories: list[str]

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that at least one changed file is under one of :attr:`directories`.

        Args:
            commit: Commit to inspect.

        Returns:
            Passing result when at least one matching file is found.  Failing
            result listing the required directories when no match exists.
        """
        prefixes = [d.rstrip("/") + "/" for d in self.directories]
        matched = [
            f for f in commit.changed_files
            if any(f.startswith(prefix) for prefix in prefixes)
        ]
        if matched:
            return CheckResult.ok(
                f"Expected directory modified — matched: {', '.join(matched)}"
            )
        return CheckResult.fail(
            f"No files modified under expected directory(ies): {', '.join(self.directories)}"
        )


# ---------------------------------------------------------------------------
# LLM checker (llama-cpp-python)
# ---------------------------------------------------------------------------

def _load_llama(config: "LlmConfig") -> object:
    """Load and return a ``Llama`` instance from the given configuration.

    Extracted as a module-level function so that tests can patch it without
    requiring llama-cpp-python to be installed.

    Args:
        config: LLM configuration specifying the model source and parameters.

    Returns:
        A ready-to-call ``llama_cpp.Llama`` instance.

    Raises:
        ImportError: If ``llama-cpp-python`` is not installed.
        ValueError: If neither ``model_path`` nor ``repo_id`` is set.
    """
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise ImportError(
            "llama-cpp-python is required for the llm checker. "
            "Install it with: pip install 'git-commit-analyzer[llm]'"
        ) from exc

    if config.model_path:
        return Llama(
            model_path=config.model_path,
            n_ctx=config.context_window,
            verbose=config.verbose,
        )
    if config.repo_id:
        return Llama.from_pretrained(
            repo_id=config.repo_id,
            filename=config.filename,
            n_ctx=config.context_window,
            verbose=config.verbose,
        )
    raise ValueError("LlmConfig requires either 'model_path' or 'repo_id' to be set")


@dataclass
class LlmChecker(CommitChecker):
    """Evaluates a commit using a local GGUF language model via llama-cpp-python.

    The model receives a rendered prompt (with ``{commit}`` substituted) and must
    reply with ``PASS`` or ``FAIL`` as the first word of its output.  Everything
    after that word is treated as the explanation and surfaced in the
    :class:`CheckResult` message.

    The model is loaded lazily on the first call and cached for subsequent
    commits, so the expensive load happens at most once per checker instance.

    Requires ``llama-cpp-python`` to be installed (optional dependency)::

        pip install 'git-commit-analyzer[llm]'

    Attributes:
        config: LLM connection and generation settings.
        include_subject: When ``True``, the commit subject line is included in
            the text substituted for ``{commit}`` in the prompt.  Defaults to
            ``True``.
        include_description: When ``True``, the commit description (body without
            trailers) is appended after the subject in the ``{commit}``
            substitution.  Ignored when the description is empty.  Defaults to
            ``True``.
        debug: When ``True``, the rendered prompt and raw model response are
            printed to *stderr* before the result is returned.
    """

    name = "llm"

    config: "LlmConfig"
    include_subject: bool = True
    include_description: bool = True
    debug: bool = False
    _llm: object = field(default=None, init=False, repr=False, compare=False)

    def _get_llm(self) -> object:
        """Return the cached ``Llama`` instance, loading it on first access."""
        if self._llm is None:
            self._llm = _load_llama(self.config)
        return self._llm

    def _build_commit_text(self, commit: GitCommit) -> str:
        """Build the text substituted for ``{commit}`` in the prompt.

        Args:
            commit: The commit being evaluated.

        Returns:
            A string containing the subject and/or description as configured.
            Returns an empty string when both flags are ``False``.
        """
        parts: list[str] = []
        if self.include_subject:
            parts.append(commit.subject)
        if self.include_description and commit.description.strip():
            parts.append(commit.description.strip())
        return "\n\n".join(parts)

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Evaluate *commit* with the configured local language model.

        Formats the prompt template (substituting ``{commit}`` with the
        selected commit text), runs inference, then parses the first word of
        the response as ``PASS`` or ``FAIL``.

        Args:
            commit: The commit to evaluate.

        Returns:
            Passing result when the model responds with ``PASS``.
            Failing result with the model's explanation when it responds with
            ``FAIL``, or an error message if the model is unavailable or the
            response is ambiguous.
        """
        commit_text = self._build_commit_text(commit)
        prompt = self.config.prompt.format(commit=commit_text)

        if self.debug:
            print(f"[debug] llm_checker model={self.config.repo_id or self.config.model_path!r}", file=sys.stderr)
            print(f"[debug] llm_checker prompt:\n{prompt}", file=sys.stderr)

        try:
            llm = self._get_llm()
            output = llm(
                prompt,
                max_tokens=self.config.max_tokens,
                stop=self.config.stop or None,
                echo=False,
            )
            response: str = output["choices"][0]["text"].strip()
        except Exception as exc:
            return CheckResult.fail(f"LLM check error: {exc}")

        if self.debug:
            print(f"[debug] llm_checker response: {response!r}", file=sys.stderr)

        words = response.split()
        first_word = words[0].upper() if words else ""
        rest = " ".join(words[1:]) if len(words) > 1 else ""

        if first_word == "PASS":
            return CheckResult.ok(rest or "LLM approved the commit")
        if first_word == "FAIL":
            return CheckResult.fail(rest or "LLM rejected the commit")
        return CheckResult.fail(
            f"LLM returned an ambiguous response (expected PASS or FAIL): {response!r}"
        )
