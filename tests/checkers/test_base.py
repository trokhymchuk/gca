from dataclasses import dataclass

import pytest

from git_commit_analyzer import (
    NegatedChecker,
    SubjectMatchesRegexChecker,
    SubjectLengthChecker,
)

from tests.checkers.conftest import MakeCommit


class TestNegatedChecker:
    def test_inverts_passing_to_failing(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: ok")
        inner = SubjectMatchesRegexChecker(pattern=r"^feat: ")
        result = NegatedChecker(checker=inner)(commit)
        assert result.passed is False
        assert "not(subject_matches_regex)" in result.message

    def test_inverts_failing_to_passing(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="WIP: do not merge")
        inner = SubjectMatchesRegexChecker(pattern=r"^WIP:")
        result = NegatedChecker(checker=inner)(commit)
        assert result.passed is False

    def test_passes_when_inner_fails(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: ok")
        inner = SubjectMatchesRegexChecker(pattern=r"^WIP:")
        result = NegatedChecker(checker=inner)(commit)
        assert result.passed is True
        assert "not(subject_matches_regex)" in result.message

    def test_dynamic_name(self) -> None:
        inner = SubjectLengthChecker(max=72)
        assert NegatedChecker(checker=inner).name == "not_subject_length"

    def test_not_in_registry(self) -> None:
        from git_commit_analyzer.checkers import CommitChecker

        assert "not_subject_length" not in CommitChecker._registry
        assert NegatedChecker.__name__ not in CommitChecker._registry


class TestCheckerNameUniqueness:
    def test_duplicate_name_raises_at_class_definition(self) -> None:
        from git_commit_analyzer.checkers import CheckResult, CommitChecker

        with pytest.raises(TypeError, match="already used"):

            @dataclass
            class DuplicateChecker(CommitChecker):
                name = "trailer_present"  # already taken

                def __call__(self, commit):
                    return CheckResult.ok()


class TestInvertViaRuleset:
    def test_invert_flag_wraps_in_negated_checker(
        self, tmp_path, make_commit: MakeCommit
    ) -> None:
        from git_commit_analyzer import load_config

        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: no-wip
    checkers:
      - type: subject_matches_regex
        pattern: "^WIP:"
        invert: true
""")
        rf = load_config(yaml_file)
        checker = rf.ruleset.rules[0].checkers[0]
        assert isinstance(checker, NegatedChecker)
        assert checker.name == "not_subject_matches_regex"

    def test_inverted_checker_passes_when_pattern_absent(
        self, tmp_path, make_commit: MakeCommit
    ) -> None:
        from git_commit_analyzer import load_config

        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: no-wip
    checkers:
      - type: subject_matches_regex
        pattern: "^WIP:"
        invert: true
""")
        rf = load_config(yaml_file)
        clean = make_commit(subject="feat: clean commit")
        wip = make_commit(subject="WIP: not ready")
        assert rf.ruleset.check_commits([clean]) == []
        failures = rf.ruleset.check_commits([wip])
        assert len(failures) == 1
