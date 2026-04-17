from git_commit_analyzer import DescriptionMatchesRegexChecker

from tests.checkers.conftest import MakeCommit


class TestDescriptionMatchesRegexChecker:
    def test_passes_on_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="This fixes the login bug.")
        result = DescriptionMatchesRegexChecker(pattern=r"fix")(commit)
        assert result.passed is True

    def test_fails_on_no_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="Refactor internals.")
        result = DescriptionMatchesRegexChecker(pattern=r"fix")(commit)
        assert result.passed is False

    def test_name(self) -> None:
        assert (
            DescriptionMatchesRegexChecker(pattern="").name
            == "description_matches_regex"
        )
