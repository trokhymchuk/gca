import pytest

from git_commit_analyzer import Trailer, TrailerPresentChecker

from tests.checkers.conftest import MakeCommit


class TestTrailerPresentRequired:
    def test_passes_when_all_required_present(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Signed-off-by", "Dev <dev@x.com>"),
                Trailer("Reviewed-by", "Alice <a@x.com>"),
            ]
        )
        result = TrailerPresentChecker(required=["Signed-off-by", "Reviewed-by"])(
            commit
        )
        assert result.passed is True

    def test_fails_when_required_missing(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Dev <dev@x.com>")])
        result = TrailerPresentChecker(required=["Signed-off-by", "Reviewed-by"])(
            commit
        )
        assert result.passed is False
        assert "Reviewed-by" in result.message

    def test_fails_when_required_is_empty(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "")])
        result = TrailerPresentChecker(required=["Signed-off-by"])(commit)
        assert result.passed is False
        assert "empty" in result.message

    def test_fails_when_required_is_whitespace(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "   ")])
        result = TrailerPresentChecker(required=["Signed-off-by"])(commit)
        assert result.passed is False
        assert "empty" in result.message

    def test_case_insensitive_token(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Dev <dev@x.com>")])
        result = TrailerPresentChecker(required=["signed-off-by"])(commit)
        assert result.passed is True


class TestTrailerPresentAtLeastOneOf:
    def test_passes_when_one_present(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Fixes", "#1")])
        result = TrailerPresentChecker(at_least_one_of=[["Fixes", "Closes"]])(commit)
        assert result.passed is True

    def test_passes_when_multiple_present(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Fixes", "#1"), Trailer("Closes", "#2")])
        result = TrailerPresentChecker(at_least_one_of=[["Fixes", "Closes"]])(commit)
        assert result.passed is True

    def test_fails_when_none_present(self, make_commit: MakeCommit) -> None:
        commit = make_commit()
        result = TrailerPresentChecker(at_least_one_of=[["Fixes", "Closes"]])(commit)
        assert result.passed is False
        assert "Fixes" in result.message
        assert "Closes" in result.message

    def test_fails_when_present_but_all_empty(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Fixes", ""), Trailer("Closes", "  ")])
        result = TrailerPresentChecker(at_least_one_of=[["Fixes", "Closes"]])(commit)
        assert result.passed is False
        assert "empty" in result.message

    def test_multiple_groups(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[Trailer("Fixes", "#1"), Trailer("Acked-by", "Alice")]
        )
        result = TrailerPresentChecker(
            at_least_one_of=[["Fixes", "Closes"], ["Acked-by", "Reviewed-by"]]
        )(commit)
        assert result.passed is True

    def test_fails_one_group_missing(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Fixes", "#1")])
        result = TrailerPresentChecker(
            at_least_one_of=[["Fixes", "Closes"], ["Acked-by", "Reviewed-by"]]
        )(commit)
        assert result.passed is False
        assert "Acked-by" in result.message


class TestTrailerPresentExactlyOneOf:
    def test_passes_when_exactly_one_present(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Co-authored-by", "Alice")])
        result = TrailerPresentChecker(
            exactly_one_of=[["Co-authored-by", "Reviewed-by"]]
        )(commit)
        assert result.passed is True

    def test_fails_when_none_present(self, make_commit: MakeCommit) -> None:
        commit = make_commit()
        result = TrailerPresentChecker(
            exactly_one_of=[["Co-authored-by", "Reviewed-by"]]
        )(commit)
        assert result.passed is False
        assert "Co-authored-by" in result.message
        assert "Reviewed-by" in result.message

    def test_fails_when_multiple_present(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Co-authored-by", "Alice"),
                Trailer("Reviewed-by", "Bob"),
            ]
        )
        result = TrailerPresentChecker(
            exactly_one_of=[["Co-authored-by", "Reviewed-by"]]
        )(commit)
        assert result.passed is False
        assert "multiple" in result.message

    def test_multiple_groups_all_pass(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[Trailer("Fixes", "#1"), Trailer("Co-authored-by", "Alice")]
        )
        result = TrailerPresentChecker(
            exactly_one_of=[
                ["Fixes", "Closes"],
                ["Co-authored-by", "Reviewed-by"],
            ]
        )(commit)
        assert result.passed is True

    def test_multiple_groups_one_fails(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Fixes", "#1"), Trailer("Closes", "#2")])
        result = TrailerPresentChecker(exactly_one_of=[["Fixes", "Closes"]])(commit)
        assert result.passed is False
        assert "multiple" in result.message


class TestTrailerPresentBlacklist:
    def test_fails_when_blacklisted_present(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("WIP", "true")])
        result = TrailerPresentChecker(blacklist=["WIP"])(commit)
        assert result.passed is False
        assert "WIP" in result.message

    def test_passes_when_blacklisted_absent(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Dev")])
        result = TrailerPresentChecker(blacklist=["WIP"])(commit)
        assert result.passed is True

    def test_case_insensitive_blacklist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("WIP", "yes")])
        result = TrailerPresentChecker(blacklist=["wip"])(commit)
        assert result.passed is False

    def test_blacklist_with_required_both_reported(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(trailers=[Trailer("WIP", "yes")])
        result = TrailerPresentChecker(required=["Signed-off-by"], blacklist=["WIP"])(
            commit
        )
        assert result.passed is False
        assert "Signed-off-by" in result.message
        assert "WIP" in result.message


class TestTrailerPresentWhitelistMode:
    def test_passes_when_only_known_trailers_in_whitelist_mode(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Dev <dev@x.com>")])
        result = TrailerPresentChecker(required=["Signed-off-by"], mode="whitelist")(
            commit
        )
        assert result.passed is True

    def test_fails_when_unlisted_trailer_in_whitelist_mode(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Signed-off-by", "Dev <dev@x.com>"),
                Trailer("Random-trailer", "value"),
            ]
        )
        result = TrailerPresentChecker(required=["Signed-off-by"], mode="whitelist")(
            commit
        )
        assert result.passed is False
        assert "Random-trailer" in result.message

    def test_whitelist_tokens_not_rejected_in_whitelist_mode(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Signed-off-by", "Dev <dev@x.com>"),
                Trailer("Change-Id", "Iabc123"),
            ]
        )
        result = TrailerPresentChecker(
            required=["Signed-off-by"],
            whitelist=["Change-Id"],
            mode="whitelist",
        )(commit)
        assert result.passed is True

    def test_at_least_one_of_tokens_allowed_in_whitelist_mode(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Signed-off-by", "Dev <dev@x.com>"),
                Trailer("Fixes", "#1"),
            ]
        )
        result = TrailerPresentChecker(
            required=["Signed-off-by"],
            at_least_one_of=[["Fixes", "Closes"]],
            mode="whitelist",
        )(commit)
        assert result.passed is True

    def test_exactly_one_of_tokens_allowed_in_whitelist_mode(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Signed-off-by", "Dev"),
                Trailer("Co-authored-by", "Alice"),
            ]
        )
        result = TrailerPresentChecker(
            required=["Signed-off-by"],
            exactly_one_of=[["Co-authored-by", "Reviewed-by"]],
            mode="whitelist",
        )(commit)
        assert result.passed is True

    def test_blacklist_mode_default_allows_unlisted(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Signed-off-by", "Dev <dev@x.com>"),
                Trailer("Random", "whatever"),
            ]
        )
        result = TrailerPresentChecker(required=["Signed-off-by"])(commit)
        assert result.passed is True


class TestTrailerPresentModeValidation:
    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="mode"):
            TrailerPresentChecker(mode="invalid")


class TestTrailerPresentCombined:
    def test_all_params_together_passes(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Signed-off-by", "Dev <dev@x.com>"),
                Trailer("Fixes", "#1"),
                Trailer("Co-authored-by", "Alice"),
                Trailer("Change-Id", "Iabc"),
            ]
        )
        result = TrailerPresentChecker(
            required=["Signed-off-by"],
            at_least_one_of=[["Fixes", "Closes"]],
            exactly_one_of=[["Co-authored-by", "Reviewed-by"]],
            whitelist=["Change-Id"],
            mode="whitelist",
        )(commit)
        assert result.passed is True

    def test_empty_params_always_passes(self, make_commit: MakeCommit) -> None:
        commit = make_commit()
        result = TrailerPresentChecker()(commit)
        assert result.passed is True

    def test_name(self) -> None:
        assert TrailerPresentChecker().name == "trailer_present"
