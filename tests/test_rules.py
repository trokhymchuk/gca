from datetime import datetime, timezone
from pathlib import Path

import pytest

from git_commit_analyzer import (
    GitCommit,
    Rule,
    Ruleset,
    Trailer,
    load_config,
)
from git_commit_analyzer.checkers import (
    SubjectMatchesRegexChecker,
    SubjectLengthChecker,
)
from git_commit_analyzer.filters import PathsModifiedFilter

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def make_commit(
    subject: str = "feat: subject",
    description: str = "",
    trailers: list[Trailer] | None = None,
    changed_files: list[str] | None = None,
) -> GitCommit:
    return GitCommit(
        sha="a" * 40,
        subject=subject,
        body="",
        description=description,
        trailers=trailers or [],
        parent_shas=[],
        changed_files=changed_files or [],
        author_name="Test",
        author_email="test@example.com",
        author_date=_NOW,
        committer_name="Test",
        committer_email="test@example.com",
        committer_date=_NOW,
    )


# ---------------------------------------------------------------------------
# Rule
# ---------------------------------------------------------------------------


class TestRule:
    def test_filtered_out_commit_returns_none(self):
        rule = Rule(
            name="src-rule",
            filters=[PathsModifiedFilter(any_of=["src/"])],
            checkers=[SubjectLengthChecker(max=10)],
        )
        commit = make_commit(changed_files=["docs/readme.md"])
        assert rule.check(commit) is None

    def test_passing_commit_returns_empty_failures(self):
        rule = Rule(
            name="conventional",
            checkers=[SubjectMatchesRegexChecker(pattern=r"^feat: ")],
        )
        commit = make_commit(subject="feat: add thing")
        result = rule.check(commit)
        assert result is not None
        assert result.passed is True
        assert result.failures == []

    def test_failing_commit_returns_failures(self):
        rule = Rule(
            name="conventional",
            checkers=[SubjectMatchesRegexChecker(pattern=r"^feat: ")],
        )
        commit = make_commit(subject="added thing")
        result = rule.check(commit)
        assert result is not None
        assert result.passed is False
        assert len(result.failures) == 1
        checker_name, message = result.failures[0]
        assert checker_name == "subject_matches_regex"
        assert "added thing" in message

    def test_multiple_checkers_all_failures_collected(self):
        rule = Rule(
            name="strict",
            checkers=[
                SubjectMatchesRegexChecker(pattern=r"^feat: "),
                SubjectLengthChecker(max=5),
            ],
        )
        commit = make_commit(subject="bad subject that is also too long")
        result = rule.check(commit)
        assert result is not None
        assert len(result.failures) == 2

    def test_no_filters_applies_to_all_commits(self):
        rule = Rule(name="all", checkers=[SubjectLengthChecker(max=72)])
        commit = make_commit(changed_files=[])
        assert rule.check(commit) is not None


# ---------------------------------------------------------------------------
# Ruleset
# ---------------------------------------------------------------------------


class TestRuleset:
    def test_returns_only_failing_results(self):
        ruleset = Ruleset(
            rules=[
                Rule(
                    name="conventional",
                    checkers=[SubjectMatchesRegexChecker(pattern=r"^feat: ")],
                ),
            ]
        )
        commits = [
            make_commit(subject="feat: good"),
            make_commit(subject="bad commit"),
        ]
        failures = ruleset.check_commits(commits)
        assert len(failures) == 1
        assert failures[0].commit.subject == "bad commit"

    def test_returns_empty_when_all_pass(self):
        ruleset = Ruleset(
            rules=[
                Rule(
                    name="conventional",
                    checkers=[SubjectMatchesRegexChecker(pattern=r"^feat: ")],
                ),
            ]
        )
        failures = ruleset.check_commits([make_commit(subject="feat: ok")])
        assert failures == []

    def test_filtered_commits_not_in_results(self):
        ruleset = Ruleset(
            rules=[
                Rule(
                    name="src-rule",
                    filters=[PathsModifiedFilter(any_of=["src/"])],
                    checkers=[SubjectMatchesRegexChecker(pattern=r"^feat: ")],
                ),
            ]
        )
        commit = make_commit(subject="bad", changed_files=["docs/readme.md"])
        assert ruleset.check_commits([commit]) == []

    def test_multiple_rules_each_can_fail_independently(self):
        ruleset = Ruleset(
            rules=[
                Rule(
                    name="rule-a",
                    checkers=[SubjectMatchesRegexChecker(pattern=r"^feat: ")],
                ),
                Rule(name="rule-b", checkers=[SubjectLengthChecker(max=5)]),
            ]
        )
        commit = make_commit(subject="bad and long subject")
        failures = ruleset.check_commits([commit])
        assert len(failures) == 2
        rule_names = {r.rule_name for r in failures}
        assert rule_names == {"rule-a", "rule-b"}


# ---------------------------------------------------------------------------
# load_config
# ---------------------------------------------------------------------------


class TestLoadRuleset:
    def test_loads_rule_with_checker(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: conventional-commits
    checkers:
      - type: subject_matches_regex
        pattern: "^(feat|fix): .+"
      - type: subject_length
        max: 72
""")
        rf = load_config(yaml_file)
        assert len(rf.ruleset.rules) == 1
        rule = rf.ruleset.rules[0]
        assert rule.name == "conventional-commits"
        assert len(rule.filters) == 0
        assert len(rule.checkers) == 2

    def test_loads_rule_with_filter_and_checker(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: src-needs-description
    filters:
      - type: paths_modified
        any_of: ["src/"]
    checkers:
      - type: description_length
        min: 20
""")
        rf = load_config(yaml_file)
        rule = rf.ruleset.rules[0]
        assert len(rule.filters) == 1
        assert len(rule.checkers) == 1

    def test_loads_multiple_rules(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: rule-a
    checkers:
      - type: subject_length
        max: 72
  - name: rule-b
    checkers:
      - type: subject_length
        min: 5
""")
        rf = load_config(yaml_file)
        assert len(rf.ruleset.rules) == 2
        assert [r.name for r in rf.ruleset.rules] == ["rule-a", "rule-b"]

    def test_unknown_checker_type_raises(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: bad
    checkers:
      - type: does_not_exist
""")
        with pytest.raises(ValueError, match="does_not_exist"):
            load_config(yaml_file)

    def test_unknown_filter_type_raises(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: bad
    filters:
      - type: does_not_exist
""")
        with pytest.raises(ValueError, match="does_not_exist"):
            load_config(yaml_file)

    def test_empty_rules_list(self, tmp_path: Path):
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("rules: []\n")
        rf = load_config(yaml_file)
        assert rf.ruleset.rules == []
