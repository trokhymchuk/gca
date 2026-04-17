import pytest

from git_commit_analyzer import CommitTypeFilter

from tests.filters.conftest import MakeCommit


class TestCommitTypeFilterFixup:
    def test_passes_for_fixup(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["fixup"])(make_commit(subject="fixup! feat: thing"))
            is True
        )

    def test_squash_does_not_match_fixup_type(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["fixup"])(
                make_commit(subject="squash! feat: thing")
            )
            is False
        )

    def test_amend_does_not_match_fixup_type(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["fixup"])(make_commit(subject="amend! feat: thing"))
            is False
        )

    def test_fails_for_normal(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["fixup"])(make_commit(subject="feat: thing"))
            is False
        )


class TestCommitTypeFilterSquash:
    def test_passes_for_squash(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["squash"])(
                make_commit(subject="squash! feat: thing")
            )
            is True
        )

    def test_fails_for_fixup(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["squash"])(
                make_commit(subject="fixup! feat: thing")
            )
            is False
        )


class TestCommitTypeFilterAmend:
    def test_passes_for_amend(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["amend"])(make_commit(subject="amend! feat: thing"))
            is True
        )

    def test_fails_for_fixup(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["amend"])(make_commit(subject="fixup! feat: thing"))
            is False
        )


class TestCommitTypeFilterMerge:
    def test_passes_for_merge(self, make_commit: MakeCommit) -> None:
        commit = make_commit(parent_shas=["aaa", "bbb"])
        assert CommitTypeFilter(types=["merge"])(commit) is True

    def test_fails_for_regular_commit(self, make_commit: MakeCommit) -> None:
        commit = make_commit(parent_shas=["aaa"])
        assert CommitTypeFilter(types=["merge"])(commit) is False


class TestCommitTypeFilterRevert:
    def test_passes_for_revert(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject='Revert "feat: add thing"')
        assert CommitTypeFilter(types=["revert"])(commit) is True

    def test_fails_for_normal_commit(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["revert"])(make_commit(subject="feat: thing"))
            is False
        )


class TestCommitTypeFilterRegular:
    def test_passes_for_normal_commit(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["regular"])(make_commit(subject="feat: thing"))
            is True
        )

    def test_fails_for_fixup(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["regular"])(
                make_commit(subject="fixup! feat: thing")
            )
            is False
        )

    def test_fails_for_squash(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["regular"])(
                make_commit(subject="squash! feat: thing")
            )
            is False
        )

    def test_fails_for_amend(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["regular"])(
                make_commit(subject="amend! feat: thing")
            )
            is False
        )

    def test_fails_for_merge(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["regular"])(make_commit(parent_shas=["aaa", "bbb"]))
            is False
        )

    def test_fails_for_revert(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["regular"])(
                make_commit(subject='Revert "feat: thing"')
            )
            is False
        )

    def test_passes_when_any_type_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit(parent_shas=["aaa", "bbb"])
        assert CommitTypeFilter(types=["fixup", "merge"])(commit) is True

    def test_fails_when_no_type_matches(self, make_commit: MakeCommit) -> None:
        assert (
            CommitTypeFilter(types=["merge", "revert"])(
                make_commit(subject="feat: thing")
            )
            is False
        )


class TestCommitTypeFilterValidation:
    def test_invalid_type_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown commit type"):
            CommitTypeFilter(types=["invalid"])

    def test_name(self) -> None:
        assert CommitTypeFilter(types=["merge"]).name == "commit_type"
