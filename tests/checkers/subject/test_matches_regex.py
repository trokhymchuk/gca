from git_commit_analyzer import SubjectMatchesRegexChecker

from tests.checkers.conftest import MakeCommit


class TestSubjectMatchesRegexChecker:
    def test_passes_on_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: add login")
        result = SubjectMatchesRegexChecker(pattern=r"^(feat|fix|chore): .+")(commit)
        assert result.passed is True

    def test_fails_on_no_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="added login")
        result = SubjectMatchesRegexChecker(pattern=r"^(feat|fix|chore): .+")(commit)
        assert result.passed is False
        assert "added login" in result.message

    def test_name(self) -> None:
        assert SubjectMatchesRegexChecker(pattern="").name == "subject_matches_regex"
