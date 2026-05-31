"""Rule and ruleset definitions, plus YAML-based ruleset loading.

A :class:`Rule` pairs a list of :class:`~git_commit_analyzer.filters.CommitFilter`
objects with a list of :class:`~git_commit_analyzer.checkers.CommitChecker` objects.
When a commit passes all filters it is checked against all checkers; any checker
failures are collected into a :class:`CommitRuleResult`.

A :class:`Ruleset` groups multiple rules and runs them all against a list of
commits, returning only the failing results.

YAML format
-----------
::

    rules:
      - name: conventional-commits
        checkers:
          - type: subject_matches_regex
            pattern: "^(feat|fix): .+"
      - name: src-needs-description
        filters:
          - type: directory_modified
            directories: ["src"]
        checkers:
          - type: description_min_length
            min_length: 20

The ``type`` value for filters and checkers must match the ``name`` class
attribute of a registered :class:`~git_commit_analyzer.filters.CommitFilter`
or :class:`~git_commit_analyzer.checkers.CommitChecker` subclass.
"""

from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from .checkers import CommitChecker, NegatedChecker
from .config import AppConfig, LlmConfig
from .filters import CommitFilter, NegatedFilter
from .models import GitCommit


@dataclass
class ConfigFile:
    """The fully parsed contents of a YAML ruleset file.

    Attributes:
        ruleset: The parsed :class:`Ruleset` containing all rules.
        config: Application configuration from the ``config:`` YAML section.
            Defaults to an :class:`~git_commit_analyzer.config.AppConfig` with
            all defaults when the section is absent.
    """

    ruleset: "Ruleset"
    config: AppConfig


@dataclass
class CommitRuleResult:
    """The outcome of running a single :class:`Rule` against a single commit.

    Attributes:
        commit: The commit that was evaluated.
        rule_name: Name of the rule that produced this result.
        failures: Ordered list of ``(checker_name, message)`` pairs for every
            checker that did not pass.  Empty when the commit satisfies all
            checkers.
    """

    commit: GitCommit
    rule_name: str
    failures: list[tuple[str, str]]

    @property
    def passed(self) -> bool:
        """``True`` when no checker failures were recorded."""
        return not self.failures


@dataclass
class Rule:
    """A named policy that combines filters with checkers.

    A commit is only evaluated by the checkers if it passes all filters.
    If it does not pass any filter it is silently skipped (not a failure).

    Attributes:
        name: Human-readable identifier shown in failure output and YAML.
        filters: Guards that decide whether a commit is in scope for this rule.
            All filters must pass for the checkers to run.  An empty list means
            the rule applies to every commit.
        checkers: Validators run against in-scope commits.  All checkers are
            always executed; failures are collected rather than short-circuited.
    """

    name: str
    filters: list[CommitFilter] = field(default_factory=list)
    checkers: list[CommitChecker] = field(default_factory=list)

    def check(self, commit: GitCommit) -> CommitRuleResult | None:
        """Evaluate this rule against a single commit.

        Args:
            commit: The commit to evaluate.

        Returns:
            ``None`` if the commit does not pass all filters (out of scope).
            A :class:`CommitRuleResult` otherwise — it may be passing
            (``result.passed is True``) or failing (``result.passed is False``).
        """
        if not all(f(commit) for f in self.filters):
            return None
        failures: list[tuple[str, str]] = []
        for checker in self.checkers:
            result = checker(commit)
            if result.passed:
                continue
            message = result.message
            if checker.fail_message:
                message = f"{message}\n{checker.fail_message}"
            failures.append((checker.name, message))
        return CommitRuleResult(commit=commit, rule_name=self.name, failures=failures)


@dataclass
class Ruleset:
    """A collection of rules applied together to a list of commits.

    Attributes:
        rules: Ordered list of :class:`Rule` objects.  Every rule is run
            against every commit independently.
    """

    rules: list[Rule]

    def check_commits(self, commits: list[GitCommit]) -> list[CommitRuleResult]:
        """Run every rule against every commit and return only failing results.

        Filtered-out commits (those that do not pass a rule's filters) are not
        included in the output.  Passing results are also omitted — the return
        value contains only actionable failures.

        Args:
            commits: List of commits to evaluate.

        Returns:
            List of :class:`CommitRuleResult` objects where ``passed`` is
            ``False``, in the order they were encountered (commit order ×
            rule order).
        """
        return list(self.iter_check_commits(commits))

    def iter_check_commits(
        self, commits: list[GitCommit]
    ) -> Iterator[CommitRuleResult]:
        """Yield failing :class:`CommitRuleResult` objects one at a time as they occur.

        Identical to :meth:`check_commits` but streams results instead of
        collecting them, allowing the caller to act on each failure immediately.
        """
        for commit in commits:
            for rule in self.rules:
                result = rule.check(commit)
                if result is not None and not result.passed:
                    yield result


def _build_filter(spec: dict) -> CommitFilter:
    """Instantiate a :class:`~git_commit_analyzer.filters.CommitFilter` from a YAML spec dict.

    Supports an optional ``invert: true`` key that wraps the resulting filter
    in a :class:`~git_commit_analyzer.filters.NegatedFilter`, making it pass
    when the inner filter fails and vice versa.

    Args:
        spec: Mapping that must contain a ``type`` key matching a registered
            filter name.  The optional ``invert`` boolean key controls negation.
            All remaining keys are passed as constructor keyword arguments.

    Returns:
        A configured filter instance, optionally wrapped in
        :class:`~git_commit_analyzer.filters.NegatedFilter`.

    Raises:
        ValueError: If ``type`` does not match any registered filter.
    """
    spec = dict(spec)
    invert = spec.pop("invert", False)
    type_name = spec.pop("type")
    cls = CommitFilter._registry.get(type_name)
    if cls is None:
        known = ", ".join(sorted(CommitFilter._registry))
        raise ValueError(f"Unknown filter type {type_name!r}. Known: {known}")
    f = cls(**spec)
    return NegatedFilter(inner=f) if invert else f


def _build_checker(
    spec: dict,
    llm_config: LlmConfig | None = None,
    debug: bool = False,
) -> CommitChecker:
    """Instantiate a :class:`~git_commit_analyzer.checkers.CommitChecker` from a YAML spec dict.

    Supports an optional ``invert: true`` key that wraps the resulting checker
    in a :class:`~git_commit_analyzer.checkers.NegatedChecker`, making the check
    pass when the inner checker fails and vice versa.

    The special ``llm`` checker type is handled separately: it requires the
    ``config.llm`` section to be present and injects the
    :class:`~git_commit_analyzer.config.LlmConfig` automatically.

    Args:
        spec: Mapping that must contain a ``type`` key matching a registered
            checker name.  The optional ``invert`` boolean key controls negation.
            All remaining keys are passed as constructor keyword arguments.
        llm_config: Parsed LLM configuration from the ``config.llm`` YAML section.
            Required when ``type`` is ``"llm"``; ignored otherwise.
        debug: Passed to :class:`~git_commit_analyzer.checkers.LlmChecker` so it
            prints diagnostic output when ``True``.

    Returns:
        A configured checker instance, optionally wrapped in
        :class:`~git_commit_analyzer.checkers.NegatedChecker`.

    Raises:
        ValueError: If ``type`` does not match any registered checker, or if
            ``type`` is ``"llm"`` but ``llm_config`` is ``None``.
    """
    spec = dict(spec)
    invert = spec.pop("invert", False)
    fail_message = spec.pop("fail_message", None)
    type_name = spec.pop("type")
    cls = CommitChecker._registry.get(type_name)
    if cls is None:
        known = ", ".join(sorted(CommitChecker._registry))
        raise ValueError(f"Unknown checker type {type_name!r}. Known: {known}")
    if type_name == "llm":
        if llm_config is None:
            raise ValueError(
                "Checker type 'llm' requires a 'config.llm' section in the YAML ruleset."
            )
        checker = cls(config=llm_config, debug=debug, **spec)
    else:
        checker = cls(**spec)
    result = NegatedChecker(checker=checker) if invert else checker
    result.fail_message = fail_message
    return result


def _build_config(config_data: dict) -> AppConfig:
    """Build an :class:`~git_commit_analyzer.config.AppConfig` from the ``config:`` YAML dict.

    Args:
        config_data: The parsed ``config:`` section, or an empty dict when the
            section is absent.

    Returns:
        A populated :class:`~git_commit_analyzer.config.AppConfig`.
    """
    llm_data = config_data.get("llm")
    llm_config: LlmConfig | None = None
    if llm_data:
        llm_config = LlmConfig(
            prompt=llm_data["prompt"],
            backend=llm_data.get("backend", "llama-cpp"),
            repo_id=llm_data.get("repo_id"),
            filename=llm_data.get("filename"),
            model_path=llm_data.get("model_path"),
            context_window=llm_data.get("context_window", 4096),
            max_tokens=llm_data.get("max_tokens", 256),
            stop=llm_data.get("stop", []),
            verbose=llm_data.get("verbose", False),
            device=llm_data.get("device", "cpu"),
            threshold=llm_data.get("threshold", 0.5),
            fail_message=llm_data.get("fail_message", ""),
        )
    return AppConfig(
        exit_code_on_failure=config_data.get("exit_code_on_failure", 1),
        debug=config_data.get("debug", False),
        llm=llm_config,
    )


def _merge_configs(configs: list[AppConfig]) -> AppConfig:
    """Merge multiple :class:`AppConfig` instances — last value wins for each field,
    except ``debug`` where any ``True`` wins."""
    if not configs:
        return AppConfig()
    result = configs[0]
    for cfg in configs[1:]:
        result = AppConfig(
            exit_code_on_failure=cfg.exit_code_on_failure,
            debug=result.debug or cfg.debug,
            llm=cfg.llm if cfg.llm is not None else result.llm,
        )
    return result


def load_configs(paths: list[Path]) -> ConfigFile:
    """Load and merge multiple YAML ruleset files into a single :class:`ConfigFile`.

    Rules are concatenated in the order the files are given.  Config sections
    are merged with last-file-wins semantics (except ``debug``, which is ``True``
    if any file enables it).

    Args:
        paths: Ordered list of YAML ruleset file paths.  Must not be empty.

    Returns:
        A :class:`ConfigFile` containing the merged :class:`Ruleset` and config.

    Raises:
        ValueError: If ``paths`` is empty, or if any file contains an error.
    """
    if not paths:
        raise ValueError("load_configs requires at least one path")
    loaded = [load_config(p) for p in paths]
    all_rules = [rule for rf in loaded for rule in rf.ruleset.rules]
    config = _merge_configs([rf.config for rf in loaded])
    return ConfigFile(ruleset=Ruleset(rules=all_rules), config=config)


def load_config(path: Path) -> ConfigFile:
    """Parse a YAML ruleset file and return a :class:`ConfigFile`.

    The YAML file may contain an optional top-level ``config:`` section (see
    :class:`~git_commit_analyzer.config.AppConfig`) in addition to the
    ``rules:`` list.

    Args:
        path: Path to the YAML file.  The file must contain a top-level
            ``rules`` list; an absent or empty list produces an empty ruleset.

    Returns:
        A :class:`ConfigFile` containing the parsed :class:`Ruleset` and
        :class:`~git_commit_analyzer.config.AppConfig`.

    Raises:
        ValueError: If any filter or checker ``type`` is not recognised, or if
            a ``llm`` checker is used without a ``config.llm`` section.
        yaml.YAMLError: If the file is not valid YAML.
        OSError: If the file cannot be opened.
    """
    with path.open() as f:
        data = yaml.safe_load(f)

    config = _build_config(data.get("config", {}) or {})

    rules = []
    for rule_data in data.get("rules", []):
        rules.append(
            Rule(
                name=rule_data["name"],
                filters=[_build_filter(spec) for spec in rule_data.get("filters", [])],
                checkers=[
                    _build_checker(spec, llm_config=config.llm, debug=config.debug)
                    for spec in rule_data.get("checkers", [])
                ],
            )
        )

    return ConfigFile(ruleset=Ruleset(rules=rules), config=config)
