from git_commit_analyzer import Trailer, TrailerCanMergeChecker

from tests.checkers.conftest import MakeCommit


class TestTrailerCanMerge:
    def test_passes_when_each_trailer_appears_once(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Co-authored-by", "Alice <a@x.com>"),
                Trailer("Signed-off-by", "Bob <b@x.com>"),
            ]
        )
        result = TrailerCanMergeChecker(trailers=["Co-authored-by", "Signed-off-by"])(
            commit
        )
        assert result.passed is True

    def test_passes_when_listed_trailer_absent(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Bob <b@x.com>")])
        result = TrailerCanMergeChecker(trailers=["Co-authored-by"])(commit)
        assert result.passed is True

    def test_fails_when_trailer_appears_twice(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Co-authored-by", "Alice <a@x.com>"),
                Trailer("Co-authored-by", "Bob <b@x.com>"),
            ]
        )
        result = TrailerCanMergeChecker(trailers=["Co-authored-by"])(commit)
        assert result.passed is False
        assert "Co-authored-by" in result.message
        assert "2" in result.message

    def test_fails_when_multiple_trailers_duplicated(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Co-authored-by", "Alice <a@x.com>"),
                Trailer("Co-authored-by", "Bob <b@x.com>"),
                Trailer("Signed-off-by", "Carol <c@x.com>"),
                Trailer("Signed-off-by", "Dave <d@x.com>"),
            ]
        )
        result = TrailerCanMergeChecker(trailers=["Co-authored-by", "Signed-off-by"])(
            commit
        )
        assert result.passed is False
        assert "Co-authored-by" in result.message
        assert "Signed-off-by" in result.message

    def test_only_listed_trailers_are_checked(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Reviewed-by", "Alice"),
                Trailer("Reviewed-by", "Bob"),
            ]
        )
        result = TrailerCanMergeChecker(trailers=["Co-authored-by"])(commit)
        assert result.passed is True

    def test_case_insensitive_token_matching(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[
                Trailer("co-authored-by", "Alice <a@x.com>"),
                Trailer("Co-Authored-By", "Bob <b@x.com>"),
            ]
        )
        result = TrailerCanMergeChecker(trailers=["Co-authored-by"])(commit)
        assert result.passed is False

    def test_passes_with_empty_trailers_list(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Co-authored-by", "Alice"),
                Trailer("Co-authored-by", "Bob"),
            ]
        )
        result = TrailerCanMergeChecker()(commit)
        assert result.passed is True

    def test_name(self) -> None:
        assert TrailerCanMergeChecker().name == "trailer_can_merge"
