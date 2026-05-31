import pytest

from git_commit_analyzer import Trailer, TrailerValueChecker

from tests.checkers.conftest import MakeCommit


class TestTrailerValueCheckerWhitelist:
    def test_passes_when_literal_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Status", "approved")])
        result = TrailerValueChecker(
            trailers=["Status"], mode="whitelist", literals=["approved"]
        )(commit)
        assert result.passed is True

    def test_fails_when_literal_does_not_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Status", "pending")])
        result = TrailerValueChecker(
            trailers=["Status"], mode="whitelist", literals=["approved"]
        )(commit)
        assert result.passed is False
        assert "pending" in result.message

    def test_fails_when_trailer_absent(self, make_commit: MakeCommit) -> None:
        commit = make_commit()
        result = TrailerValueChecker(
            trailers=["Status"], mode="whitelist", literals=["approved"]
        )(commit)
        assert result.passed is False
        assert "absent" in result.message

    def test_passes_when_regexp_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Fixes", "JIRA-123")])
        result = TrailerValueChecker(
            trailers=["Fixes"], mode="whitelist", regexps=[r"^JIRA-\d+$"]
        )(commit)
        assert result.passed is True

    def test_fails_when_regexp_does_not_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Fixes", "#42")])
        result = TrailerValueChecker(
            trailers=["Fixes"], mode="whitelist", regexps=[r"^JIRA-\d+$"]
        )(commit)
        assert result.passed is False

    def test_passes_when_any_literal_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Status", "merged")])
        result = TrailerValueChecker(
            trailers=["Status"], mode="whitelist", literals=["approved", "merged"]
        )(commit)
        assert result.passed is True

    def test_passes_when_any_trailer_value_matches(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[Trailer("Status", "pending"), Trailer("Status", "approved")]
        )
        result = TrailerValueChecker(
            trailers=["Status"], mode="whitelist", literals=["approved"]
        )(commit)
        assert result.passed is True

    def test_literal_match_is_case_sensitive(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Status", "Approved")])
        result = TrailerValueChecker(
            trailers=["Status"], mode="whitelist", literals=["approved"]
        )(commit)
        assert result.passed is False

    def test_token_match_is_case_insensitive(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("status", "approved")])
        result = TrailerValueChecker(
            trailers=["Status"], mode="whitelist", literals=["approved"]
        )(commit)
        assert result.passed is True

    def test_passes_when_literal_or_regexp_matches(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(trailers=[Trailer("Fixes", "JIRA-42")])
        result = TrailerValueChecker(
            trailers=["Fixes"], mode="whitelist", literals=["#1"], regexps=[r"JIRA-\d+"]
        )(commit)
        assert result.passed is True

    def test_all_trailers_must_pass(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Fixes", "JIRA-1")])
        result = TrailerValueChecker(
            trailers=["Fixes", "Closes"], mode="whitelist", regexps=[r"^JIRA-\d+$"]
        )(commit)
        assert result.passed is False
        assert "Closes" in result.message

    def test_passes_when_all_trailers_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[Trailer("Fixes", "JIRA-1"), Trailer("Closes", "JIRA-2")]
        )
        result = TrailerValueChecker(
            trailers=["Fixes", "Closes"], mode="whitelist", regexps=[r"^JIRA-\d+$"]
        )(commit)
        assert result.passed is True

    def test_error_message_lists_all_failing_trailers(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit()
        result = TrailerValueChecker(
            trailers=["Fixes", "Closes"], mode="whitelist", literals=["JIRA-1"]
        )(commit)
        assert result.passed is False
        assert "Fixes" in result.message
        assert "Closes" in result.message


class TestTrailerValueCheckerBlacklist:
    def test_passes_when_trailer_absent(self, make_commit: MakeCommit) -> None:
        commit = make_commit()
        result = TrailerValueChecker(
            trailers=["WIP"], mode="blacklist", literals=["true"]
        )(commit)
        assert result.passed is True

    def test_passes_when_value_does_not_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("WIP", "false")])
        result = TrailerValueChecker(
            trailers=["WIP"], mode="blacklist", literals=["true"]
        )(commit)
        assert result.passed is True

    def test_fails_when_literal_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("WIP", "true")])
        result = TrailerValueChecker(
            trailers=["WIP"], mode="blacklist", literals=["true"]
        )(commit)
        assert result.passed is False
        assert "true" in result.message

    def test_fails_when_regexp_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "bot@example.com")])
        result = TrailerValueChecker(
            trailers=["Signed-off-by"], mode="blacklist", regexps=[r"bot@example\.com"]
        )(commit)
        assert result.passed is False

    def test_passes_when_regexp_does_not_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "dev@example.com")])
        result = TrailerValueChecker(
            trailers=["Signed-off-by"], mode="blacklist", regexps=[r"bot@example\.com"]
        )(commit)
        assert result.passed is True

    def test_fails_when_any_value_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[Trailer("Status", "ok"), Trailer("Status", "wip")]
        )
        result = TrailerValueChecker(
            trailers=["Status"], mode="blacklist", literals=["wip"]
        )(commit)
        assert result.passed is False

    def test_all_trailers_must_pass(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("WIP", "true")])
        result = TrailerValueChecker(
            trailers=["WIP", "Skip-CI"], mode="blacklist", literals=["true"]
        )(commit)
        assert result.passed is False
        assert "WIP" in result.message

    def test_passes_when_all_trailers_clear(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[Trailer("WIP", "false"), Trailer("Skip-CI", "false")]
        )
        result = TrailerValueChecker(
            trailers=["WIP", "Skip-CI"], mode="blacklist", literals=["true"]
        )(commit)
        assert result.passed is True


class TestTrailerValueCheckerValidation:
    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="mode"):
            TrailerValueChecker(trailers=["X"], mode="invalid", literals=["v"])

    def test_no_literals_or_regexps_raises(self) -> None:
        with pytest.raises(ValueError, match="literals.*regexps|regexps.*literals"):
            TrailerValueChecker(trailers=["X"], mode="whitelist")

    def test_name(self) -> None:
        assert (
            TrailerValueChecker(trailers=["X"], mode="whitelist", literals=["v"]).name
            == "trailer_value"
        )

    def test_repr(self) -> None:
        f = TrailerValueChecker(
            trailers=["Status", "WIP"], mode="whitelist", literals=["approved"]
        )
        assert "Status" in repr(f)
        assert "WIP" in repr(f)
        assert "whitelist" in repr(f)
        assert "approved" in repr(f)
