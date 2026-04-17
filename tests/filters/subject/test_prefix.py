from git_commit_analyzer import SubjectPrefixFilter

from tests.filters.conftest import MakeCommit


class TestSubjectPrefixFilterAnyOf:
    def test_passes_single_prefix_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: add thing")
        assert SubjectPrefixFilter(any_of=[["feat"]])(commit) is True

    def test_fails_no_matching_chain(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="custom: add thing")
        assert SubjectPrefixFilter(any_of=[["feat"], ["fix"]])(commit) is False

    def test_passes_chained_prefix(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="ci: cram: add test")
        assert SubjectPrefixFilter(any_of=[["ci", "cram"]])(commit) is True

    def test_passes_one_of_two_chains(self, make_commit: MakeCommit) -> None:
        filter_ = SubjectPrefixFilter(any_of=[["ci", "cram"], ["feat"]])
        assert filter_(make_commit(subject="ci: cram: add test")) is True
        assert filter_(make_commit(subject="feat: add thing")) is True

    def test_fails_partial_chain(self, make_commit: MakeCommit) -> None:
        # chain [ci] does not match pattern [ci, cram]
        commit = make_commit(subject="ci: add test")
        assert SubjectPrefixFilter(any_of=[["ci", "cram"]])(commit) is False

    def test_case_insensitive_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="FEAT: add thing")
        assert SubjectPrefixFilter(any_of=[["feat"]])(commit) is True

    def test_no_prefix_no_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="plain message without prefix")
        assert SubjectPrefixFilter(any_of=[["feat"]])(commit) is False

    def test_conventional_prefix_recognised(self, make_commit: MakeCommit) -> None:
        # filter accepts both conventional and non-conventional
        commit = make_commit(subject="feat(api): add endpoint")
        assert SubjectPrefixFilter(any_of=[["feat"]])(commit) is True

    def test_conventional_chain_recognised(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="ci(gh): cram(unit): add test")
        assert SubjectPrefixFilter(any_of=[["ci", "cram"]])(commit) is True


class TestSubjectPrefixFilterAllOf:
    def test_passes_when_chain_matches_single_pattern(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="feat: add thing")
        assert SubjectPrefixFilter(all_of=[["feat"]])(commit) is True

    def test_fails_when_chain_does_not_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="fix: patch")
        assert SubjectPrefixFilter(all_of=[["feat"]])(commit) is False

    def test_passes_chain_matches_all_same_pattern(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="ci: cram: add test")
        # both patterns are the same chain — passes
        assert (
            SubjectPrefixFilter(all_of=[["ci", "cram"], ["ci", "cram"]])(commit) is True
        )

    def test_fails_chain_cannot_match_two_different_patterns(
        self, make_commit: MakeCommit
    ) -> None:
        # chain [feat] cannot simultaneously equal [feat] and [fix]
        commit = make_commit(subject="feat: add thing")
        assert SubjectPrefixFilter(all_of=[["feat"], ["fix"]])(commit) is False


class TestSubjectPrefixFilterCombined:
    def test_any_of_and_all_of_both_must_hold(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="ci: cram: add test")
        assert (
            SubjectPrefixFilter(
                any_of=[["ci", "cram"], ["feat"]],
                all_of=[["ci", "cram"]],
            )(commit)
            is True
        )

    def test_any_of_fails_stops_pass(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="fix: patch")
        assert (
            SubjectPrefixFilter(
                any_of=[["ci", "cram"], ["feat"]],
                all_of=[["fix"]],
            )(commit)
            is False
        )

    def test_empty_params_never_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: thing")
        assert SubjectPrefixFilter()(commit) is False

    def test_name(self) -> None:
        assert SubjectPrefixFilter().name == "subject_prefix"
