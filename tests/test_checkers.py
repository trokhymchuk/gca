from dataclasses import dataclass
from datetime import datetime, timezone

import pytest

from git_commit_analyzer import (
    AnyTrailerPresentChecker,
    DescriptionLineMaxLengthChecker,
    DescriptionMatchesRegexChecker,
    DescriptionMinLengthChecker,
    DirectoryModifiedChecker,
    FileModifiedChecker,
    GitCommit,
    NegatedChecker,
    OnlyDirectoriesModifiedChecker,
    OnlyFilesModifiedChecker,
    SubjectMatchesRegexChecker,
    SubjectMaxLengthChecker,
    SubjectMinLengthChecker,
    TrailerPresentChecker,
    Trailer,
)

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
# TrailerPresentChecker
# ---------------------------------------------------------------------------

class TestTrailerPresentChecker:
    def test_passes_when_trailer_present(self):
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Dev <dev@x.com>")])
        result = TrailerPresentChecker(token="Signed-off-by")(commit)
        assert result.passed is True

    def test_fails_when_trailer_missing(self):
        commit = make_commit()
        result = TrailerPresentChecker(token="Signed-off-by")(commit)
        assert result.passed is False
        assert "Signed-off-by" in result.message

    def test_fails_when_trailer_value_is_empty(self):
        commit = make_commit(trailers=[Trailer("Signed-off-by", "")])
        result = TrailerPresentChecker(token="Signed-off-by")(commit)
        assert result.passed is False
        assert "empty" in result.message

    def test_fails_when_trailer_value_is_whitespace(self):
        commit = make_commit(trailers=[Trailer("Signed-off-by", "   ")])
        result = TrailerPresentChecker(token="Signed-off-by")(commit)
        assert result.passed is False
        assert "empty" in result.message

    def test_case_insensitive_token(self):
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Dev <dev@x.com>")])
        result = TrailerPresentChecker(token="signed-off-by")(commit)
        assert result.passed is True

    def test_name(self):
        assert TrailerPresentChecker(token="Fixes").name == "trailer_present"


# ---------------------------------------------------------------------------
# AnyTrailerPresentChecker
# ---------------------------------------------------------------------------

class TestAnyTrailerPresentChecker:
    def test_passes_when_one_present(self):
        commit = make_commit(trailers=[Trailer("Fixes", "#1")])
        result = AnyTrailerPresentChecker(tokens=["Fixes", "Closes"])(commit)
        assert result.passed is True

    def test_passes_when_multiple_present(self):
        commit = make_commit(trailers=[Trailer("Fixes", "#1"), Trailer("Closes", "#2")])
        result = AnyTrailerPresentChecker(tokens=["Fixes", "Closes"])(commit)
        assert result.passed is True

    def test_fails_when_none_present(self):
        commit = make_commit()
        result = AnyTrailerPresentChecker(tokens=["Fixes", "Closes"])(commit)
        assert result.passed is False
        assert "Fixes" in result.message
        assert "Closes" in result.message

    def test_fails_when_present_but_all_empty(self):
        commit = make_commit(trailers=[Trailer("Fixes", ""), Trailer("Closes", "  ")])
        result = AnyTrailerPresentChecker(tokens=["Fixes", "Closes"])(commit)
        assert result.passed is False
        assert "empty" in result.message

    def test_name(self):
        assert AnyTrailerPresentChecker(tokens=[]).name == "any_trailer_present"


# ---------------------------------------------------------------------------
# SubjectMatchesRegexChecker
# ---------------------------------------------------------------------------

class TestSubjectMatchesRegexChecker:
    def test_passes_on_match(self):
        commit = make_commit(subject="feat: add login")
        result = SubjectMatchesRegexChecker(pattern=r"^(feat|fix|chore): .+")(commit)
        assert result.passed is True

    def test_fails_on_no_match(self):
        commit = make_commit(subject="added login")
        result = SubjectMatchesRegexChecker(pattern=r"^(feat|fix|chore): .+")(commit)
        assert result.passed is False
        assert "added login" in result.message

    def test_name(self):
        assert SubjectMatchesRegexChecker(pattern="").name == "subject_matches_regex"


# ---------------------------------------------------------------------------
# SubjectMaxLengthChecker
# ---------------------------------------------------------------------------

class TestSubjectMaxLengthChecker:
    def test_passes_when_equal_to_limit(self):
        commit = make_commit(subject="a" * 72)
        assert SubjectMaxLengthChecker(max_length=72)(commit).passed is True

    def test_passes_when_under_limit(self):
        commit = make_commit(subject="short")
        assert SubjectMaxLengthChecker(max_length=72)(commit).passed is True

    def test_fails_when_over_limit(self):
        commit = make_commit(subject="a" * 73)
        result = SubjectMaxLengthChecker(max_length=72)(commit)
        assert result.passed is False
        assert "73" in result.message
        assert "72" in result.message

    def test_name(self):
        assert SubjectMaxLengthChecker(max_length=72).name == "subject_max_length"


# ---------------------------------------------------------------------------
# SubjectMinLengthChecker
# ---------------------------------------------------------------------------

class TestSubjectMinLengthChecker:
    def test_passes_when_equal_to_limit(self):
        commit = make_commit(subject="a" * 10)
        assert SubjectMinLengthChecker(min_length=10)(commit).passed is True

    def test_passes_when_over_limit(self):
        commit = make_commit(subject="long enough subject")
        assert SubjectMinLengthChecker(min_length=5)(commit).passed is True

    def test_fails_when_under_limit(self):
        commit = make_commit(subject="hi")
        result = SubjectMinLengthChecker(min_length=10)(commit)
        assert result.passed is False
        assert "2" in result.message
        assert "10" in result.message

    def test_name(self):
        assert SubjectMinLengthChecker(min_length=1).name == "subject_min_length"


# ---------------------------------------------------------------------------
# DescriptionMatchesRegexChecker
# ---------------------------------------------------------------------------

class TestDescriptionMatchesRegexChecker:
    def test_passes_on_match(self):
        commit = make_commit(description="This fixes the login bug.")
        result = DescriptionMatchesRegexChecker(pattern=r"fix")(commit)
        assert result.passed is True

    def test_fails_on_no_match(self):
        commit = make_commit(description="Refactor internals.")
        result = DescriptionMatchesRegexChecker(pattern=r"fix")(commit)
        assert result.passed is False

    def test_name(self):
        assert DescriptionMatchesRegexChecker(pattern="").name == "description_matches_regex"


# ---------------------------------------------------------------------------
# DescriptionMinLengthChecker
# ---------------------------------------------------------------------------

class TestDescriptionMinLengthChecker:
    def test_passes_when_long_enough(self):
        commit = make_commit(description="Enough detail here.")
        assert DescriptionMinLengthChecker(min_length=10)(commit).passed is True

    def test_fails_when_too_short(self):
        commit = make_commit(description="")
        result = DescriptionMinLengthChecker(min_length=10)(commit)
        assert result.passed is False

    def test_name(self):
        assert DescriptionMinLengthChecker(min_length=1).name == "description_min_length"


# ---------------------------------------------------------------------------
# DescriptionLineMaxLengthChecker
# ---------------------------------------------------------------------------

class TestDescriptionLineMaxLengthChecker:
    def test_passes_when_all_lines_within_limit(self):
        commit = make_commit(description="Short line.\nAlso short.")
        assert DescriptionLineMaxLengthChecker(max_length=72)(commit).passed is True

    def test_fails_on_first_long_line(self):
        long_line = "x" * 100
        commit = make_commit(description=f"Fine line.\n{long_line}\nFine again.")
        result = DescriptionLineMaxLengthChecker(max_length=72)(commit)
        assert result.passed is False
        assert "100" in result.message
        assert "72" in result.message
        assert "line 2" in result.message.lower()

    def test_empty_description_passes(self):
        commit = make_commit(description="")
        assert DescriptionLineMaxLengthChecker(max_length=72)(commit).passed is True

    def test_name(self):
        assert DescriptionLineMaxLengthChecker(max_length=72).name == "description_line_max_length"


# ---------------------------------------------------------------------------
# OnlyFilesModifiedChecker
# ---------------------------------------------------------------------------

class TestOnlyFilesModifiedChecker:
    def test_passes_when_all_files_allowed(self):
        commit = make_commit(changed_files=["a.py", "b.py"])
        result = OnlyFilesModifiedChecker(files=["a.py", "b.py", "c.py"])(commit)
        assert result.passed is True

    def test_fails_when_unexpected_file_present(self):
        commit = make_commit(changed_files=["a.py", "secret.env"])
        result = OnlyFilesModifiedChecker(files=["a.py"])(commit)
        assert result.passed is False
        assert "secret.env" in result.message

    def test_passes_with_no_changed_files(self):
        commit = make_commit(changed_files=[])
        assert OnlyFilesModifiedChecker(files=["a.py"])(commit).passed is True

    def test_name(self):
        assert OnlyFilesModifiedChecker(files=[]).name == "only_files_modified"


# ---------------------------------------------------------------------------
# OnlyDirectoriesModifiedChecker
# ---------------------------------------------------------------------------

class TestCheckerNameUniqueness:
    def test_duplicate_name_raises_at_class_definition(self):
        from git_commit_analyzer.checkers import CommitChecker, CheckResult

        with pytest.raises(TypeError, match="already used"):
            @dataclass
            class DuplicateChecker(CommitChecker):
                name = "trailer_present"  # already taken

                def __call__(self, commit):
                    return CheckResult.ok()


class TestOnlyDirectoriesModifiedChecker:
    def test_passes_when_all_files_within_dirs(self):
        commit = make_commit(changed_files=["src/a.py", "src/b.py"])
        assert OnlyDirectoriesModifiedChecker(directories=["src"])(commit).passed is True

    def test_fails_when_file_outside_dirs(self):
        commit = make_commit(changed_files=["src/a.py", "docs/readme.md"])
        result = OnlyDirectoriesModifiedChecker(directories=["src"])(commit)
        assert result.passed is False
        assert "docs/readme.md" in result.message

    def test_trailing_slash_normalised(self):
        commit = make_commit(changed_files=["lib/util.py"])
        assert OnlyDirectoriesModifiedChecker(directories=["lib/"])(commit).passed is True

    def test_passes_with_no_changed_files(self):
        commit = make_commit(changed_files=[])
        assert OnlyDirectoriesModifiedChecker(directories=["src"])(commit).passed is True

    def test_name(self):
        assert OnlyDirectoriesModifiedChecker(directories=[]).name == "only_directories_modified"


# ---------------------------------------------------------------------------
# FileModifiedChecker
# ---------------------------------------------------------------------------

class TestFileModifiedChecker:
    def test_passes_when_expected_file_modified(self):
        commit = make_commit(changed_files=["CHANGELOG.md"])
        assert FileModifiedChecker(files=["CHANGELOG.md"])(commit).passed is True

    def test_passes_when_any_of_list_modified(self):
        commit = make_commit(changed_files=["b.py"])
        assert FileModifiedChecker(files=["a.py", "b.py"])(commit).passed is True

    def test_fails_when_none_of_files_modified(self):
        commit = make_commit(changed_files=["unrelated.py"])
        result = FileModifiedChecker(files=["CHANGELOG.md"])(commit)
        assert result.passed is False
        assert "CHANGELOG.md" in result.message

    def test_fails_with_no_changed_files(self):
        commit = make_commit(changed_files=[])
        assert FileModifiedChecker(files=["a.py"])(commit).passed is False

    def test_name(self):
        assert FileModifiedChecker(files=[]).name == "file_modified"


# ---------------------------------------------------------------------------
# DirectoryModifiedChecker
# ---------------------------------------------------------------------------

class TestDirectoryModifiedChecker:
    def test_passes_when_file_in_directory_modified(self):
        commit = make_commit(changed_files=["src/main.py"])
        assert DirectoryModifiedChecker(directories=["src"])(commit).passed is True

    def test_passes_when_nested_file_modified(self):
        commit = make_commit(changed_files=["src/pkg/module.py"])
        assert DirectoryModifiedChecker(directories=["src"])(commit).passed is True

    def test_fails_when_no_files_in_directory_modified(self):
        commit = make_commit(changed_files=["docs/readme.md"])
        result = DirectoryModifiedChecker(directories=["src"])(commit)
        assert result.passed is False
        assert "src" in result.message

    def test_passes_when_any_directory_matches(self):
        commit = make_commit(changed_files=["tests/test_foo.py"])
        assert DirectoryModifiedChecker(directories=["src", "tests"])(commit).passed is True

    def test_trailing_slash_normalised(self):
        commit = make_commit(changed_files=["lib/util.py"])
        assert DirectoryModifiedChecker(directories=["lib/"])(commit).passed is True

    def test_fails_with_no_changed_files(self):
        commit = make_commit(changed_files=[])
        assert DirectoryModifiedChecker(directories=["src"])(commit).passed is False

    def test_name(self):
        assert DirectoryModifiedChecker(directories=[]).name == "directory_modified"


# ---------------------------------------------------------------------------
# NegatedChecker
# ---------------------------------------------------------------------------

class TestNegatedChecker:
    def test_inverts_passing_to_failing(self):
        commit = make_commit(subject="feat: ok")
        inner = SubjectMatchesRegexChecker(pattern=r"^feat: ")
        result = NegatedChecker(checker=inner)(commit)
        assert result.passed is False
        assert "not(subject_matches_regex)" in result.message

    def test_inverts_failing_to_passing(self):
        commit = make_commit(subject="WIP: do not merge")
        inner = SubjectMatchesRegexChecker(pattern=r"^WIP:")
        result = NegatedChecker(checker=inner)(commit)
        # inner passes → negated fails
        assert result.passed is False

    def test_passes_when_inner_fails(self):
        commit = make_commit(subject="feat: ok")
        inner = SubjectMatchesRegexChecker(pattern=r"^WIP:")
        result = NegatedChecker(checker=inner)(commit)
        # inner fails (no match) → negated passes
        assert result.passed is True
        assert "not(subject_matches_regex)" in result.message

    def test_dynamic_name(self):
        inner = SubjectMaxLengthChecker(max_length=72)
        assert NegatedChecker(checker=inner).name == "not_subject_max_length"

    def test_not_in_registry(self):
        from git_commit_analyzer.checkers import CommitChecker
        assert "not_subject_max_length" not in CommitChecker._registry
        assert NegatedChecker.__name__ not in CommitChecker._registry


# ---------------------------------------------------------------------------
# invert: true via YAML / _build_checker
# ---------------------------------------------------------------------------

class TestInvertViaRuleset:
    def test_invert_flag_wraps_in_negated_checker(self, tmp_path):
        from pathlib import Path
        from git_commit_analyzer import load_ruleset

        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: no-wip
    checkers:
      - type: subject_matches_regex
        pattern: "^WIP:"
        invert: true
""")
        rf = load_ruleset(yaml_file)
        checker = rf.ruleset.rules[0].checkers[0]
        assert isinstance(checker, NegatedChecker)
        assert checker.name == "not_subject_matches_regex"

    def test_inverted_checker_passes_when_pattern_absent(self, tmp_path):
        from pathlib import Path
        from git_commit_analyzer import load_ruleset

        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: no-wip
    checkers:
      - type: subject_matches_regex
        pattern: "^WIP:"
        invert: true
""")
        rf = load_ruleset(yaml_file)
        clean = make_commit(subject="feat: clean commit")
        wip = make_commit(subject="WIP: not ready")
        assert rf.ruleset.check_commits([clean]) == []
        failures = rf.ruleset.check_commits([wip])
        assert len(failures) == 1
