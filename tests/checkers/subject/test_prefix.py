import pytest

from git_commit_analyzer import SubjectPrefixChecker

from tests.checkers.conftest import MakeCommit


class TestSubjectPrefixRequirePrefix:
    def test_passes_with_valid_prefix(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: add feature")
        result = SubjectPrefixChecker()(commit)
        assert result.passed is True

    def test_passes_prefix_with_hyphen(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="hot-fix: urgent change")
        result = SubjectPrefixChecker()(commit)
        assert result.passed is True

    def test_fails_when_no_prefix_and_required(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="add feature without prefix")
        result = SubjectPrefixChecker()(commit)
        assert result.passed is False
        assert "no valid prefix" in result.message

    def test_passes_when_no_prefix_and_not_required(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="add feature without prefix")
        result = SubjectPrefixChecker(require_prefix=False)(commit)
        assert result.passed is True

    def test_prefix_chain_in_message(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="chore: update deps")
        result = SubjectPrefixChecker()(commit)
        assert result.passed is True
        assert "chore" in result.message


class TestSubjectPrefixConventional:
    def test_passes_with_scope(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat(api): add endpoint")
        result = SubjectPrefixChecker(conventional=True)(commit)
        assert result.passed is True

    def test_fails_without_scope_when_conventional(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="feat: add feature")
        result = SubjectPrefixChecker(conventional=True)(commit)
        assert result.passed is False
        assert "prefix(scope)" in result.message

    def test_fails_no_prefix_at_all_conventional(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="just a plain message")
        result = SubjectPrefixChecker(conventional=True)(commit)
        assert result.passed is False

    def test_passes_not_required_no_prefix_conventional(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="plain message")
        result = SubjectPrefixChecker(require_prefix=False, conventional=True)(commit)
        assert result.passed is True

    def test_conventional_with_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat(ui): add button")
        result = SubjectPrefixChecker(conventional=True, whitelist=[["feat"], ["fix"]])(
            commit
        )
        assert result.passed is True

    def test_conventional_with_whitelist_fails_unlisted(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="custom(api): do thing")
        result = SubjectPrefixChecker(conventional=True, whitelist=[["feat"], ["fix"]])(
            commit
        )
        assert result.passed is False
        assert "custom" in result.message


class TestSubjectPrefixWhitelistOnly:
    def test_passes_when_chain_in_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: add feature")
        result = SubjectPrefixChecker(whitelist=[["feat"], ["fix"], ["chore"]])(commit)
        assert result.passed is True

    def test_fails_when_chain_not_in_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="custom: do something")
        result = SubjectPrefixChecker(whitelist=[["feat"], ["fix"]])(commit)
        assert result.passed is False
        assert "custom" in result.message

    def test_whitelist_match_is_case_insensitive(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="FEAT: add feature")
        result = SubjectPrefixChecker(whitelist=[["feat"]])(commit)
        assert result.passed is True

    def test_default_mode_is_whitelist_when_only_whitelist_set(self) -> None:
        checker = SubjectPrefixChecker(whitelist=[["feat"]])
        assert checker._effective_mode() == "whitelist"

    def test_no_prefix_required_not_in_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="plain message")
        result = SubjectPrefixChecker(require_prefix=False, whitelist=[["feat"]])(
            commit
        )
        assert result.passed is True


class TestSubjectPrefixBlacklistOnly:
    def test_passes_when_chain_not_in_blacklist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: add feature")
        result = SubjectPrefixChecker(blacklist=[["WIP"]])(commit)
        assert result.passed is True

    def test_fails_when_chain_in_blacklist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="WIP: not ready")
        result = SubjectPrefixChecker(blacklist=[["WIP"]])(commit)
        assert result.passed is False
        assert "WIP" in result.message

    def test_blacklist_match_is_case_insensitive(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="wip: in progress")
        result = SubjectPrefixChecker(blacklist=[["WIP"]])(commit)
        assert result.passed is False

    def test_default_mode_is_blacklist_when_only_blacklist_set(self) -> None:
        checker = SubjectPrefixChecker(blacklist=[["WIP"]])
        assert checker._effective_mode() == "blacklist"

    def test_default_mode_is_blacklist_when_neither_set(self) -> None:
        checker = SubjectPrefixChecker()
        assert checker._effective_mode() == "blacklist"

    def test_no_config_passes_any_prefix(self, make_commit: MakeCommit) -> None:
        # blacklist mode with empty blacklist → any prefix allowed
        commit = make_commit(subject="anything: goes")
        result = SubjectPrefixChecker()(commit)
        assert result.passed is True

    def test_unlisted_chain_allowed_in_blacklist_mode(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="custom: my thing")
        result = SubjectPrefixChecker(blacklist=[["WIP"]])(commit)
        assert result.passed is True

    def test_fails_if_blacklist_is_empty_and_no_prefix(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="update something")
        result = SubjectPrefixChecker()(commit)
        assert result.passed is False


class TestSubjectPrefixBothWithMode:
    def test_raises_when_both_set_without_mode(self) -> None:
        with pytest.raises(ValueError, match="mode"):
            SubjectPrefixChecker(whitelist=[["feat"]], blacklist=[["WIP"]])

    def test_mode_whitelist_enforces_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="custom: thing")
        result = SubjectPrefixChecker(
            whitelist=[["feat"], ["fix"]],
            blacklist=[["WIP"]],
            mode="whitelist",
        )(commit)
        assert result.passed is False
        assert "custom" in result.message

    def test_mode_whitelist_still_rejects_blacklisted(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="WIP: draft")
        result = SubjectPrefixChecker(
            whitelist=[["feat"], ["WIP"]],
            blacklist=[["WIP"]],
            mode="whitelist",
        )(commit)
        assert result.passed is False
        assert "WIP" in result.message

    def test_mode_blacklist_allows_unlisted(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="custom: thing")
        result = SubjectPrefixChecker(
            whitelist=[["feat"]],
            blacklist=[["WIP"]],
            mode="blacklist",
        )(commit)
        assert result.passed is True

    def test_mode_blacklist_still_rejects_blacklisted(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="WIP: draft")
        result = SubjectPrefixChecker(
            whitelist=[["feat"]],
            blacklist=[["WIP"]],
            mode="blacklist",
        )(commit)
        assert result.passed is False

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="mode"):
            SubjectPrefixChecker(mode="invalid")


class TestSubjectPrefixChains:
    def test_chain_in_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="ci: cram: add new test")
        result = SubjectPrefixChecker(whitelist=[["ci", "cram"]])(commit)
        assert result.passed is True

    def test_chain_in_required(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="ci: cram: add new test")
        result = SubjectPrefixChecker(required=[["ci", "cram"]])(commit)
        assert result.passed is True

    def test_chain_in_required_any_position(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="PROVISORY: ci: cram: add new test")
        result = SubjectPrefixChecker(required=[["ci", "cram"]])(commit)
        assert result.passed is True

    def test_chain_or_single_whitelist(self, make_commit: MakeCommit) -> None:
        checker = SubjectPrefixChecker(whitelist=[["ci", "cram"], ["feat"]])
        assert checker(make_commit(subject="ci: cram: add test")).passed is True
        assert checker(make_commit(subject="ci: cram: add test")).passed is True
        assert checker(make_commit(subject="feat: add thing")).passed is True
        assert checker(make_commit(subject="ci: add thing")).passed is False

    def test_partial_chain_does_not_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="ci: add test")
        result = SubjectPrefixChecker(whitelist=[["ci", "cram"]])(commit)
        assert result.passed is False

    def test_chain_blacklist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="ci: cram: draft")
        result = SubjectPrefixChecker(blacklist=[["ci", "cram"]])(commit)
        assert result.passed is False
        assert "ci: cram:" in result.message

    def test_three_prefix_chain(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: ci: cram: some message")
        result = SubjectPrefixChecker(whitelist=[["feat", "ci", "cram"]])(commit)
        assert result.passed is True

    def test_conventional_chain(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="ci(gh): cram(unit): add test")
        result = SubjectPrefixChecker(conventional=True, whitelist=[["ci", "cram"]])(
            commit
        )
        assert result.passed is True


class TestSubjectPrefixMisc:
    def test_empty_params_passes_any_prefix(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="anything: goes here")
        result = SubjectPrefixChecker()(commit)
        assert result.passed is True

    def test_name(self) -> None:
        assert SubjectPrefixChecker().name == "subject_prefix"


class TestSubjectPrefixRequired:
    """required: list[list[str]] — OR across outer list, contiguous subsequence per inner list."""

    def test_single_token_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="ci: add pipeline")
        result = SubjectPrefixChecker(required=[["ci"]])(commit)
        assert result.passed is True

    def test_single_token_no_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: add feature")
        result = SubjectPrefixChecker(required=[["ci"]])(commit)
        assert result.passed is False
        assert "ci" in result.message

    def test_or_semantics_first_alternative_matches(
        self, make_commit: MakeCommit
    ) -> None:
        # [["ci"], ["cram"]] → ci OR cram; chain is ["ci"] → PASS
        commit = make_commit(subject="ci: add pipeline")
        result = SubjectPrefixChecker(required=[["ci"], ["cram"]])(commit)
        assert result.passed is True

    def test_or_semantics_second_alternative_matches(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="cram: add test")
        result = SubjectPrefixChecker(required=[["ci"], ["cram"]])(commit)
        assert result.passed is True

    def test_or_semantics_both_present_passes(self, make_commit: MakeCommit) -> None:
        # chain contains both ci and cram → satisfies either pattern → PASS
        commit = make_commit(subject="ci: cram: add test")
        result = SubjectPrefixChecker(required=[["ci"], ["cram"]])(commit)
        assert result.passed is True

    def test_or_semantics_neither_present_fails(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: add thing")
        result = SubjectPrefixChecker(required=[["ci"], ["cram"]])(commit)
        assert result.passed is False

    def test_subsequence_requires_exact_consecutive_tokens(
        self, make_commit: MakeCommit
    ) -> None:
        # [["ci", "cram"]] requires ci: cram: as contiguous pair → PASS
        commit = make_commit(subject="ci: cram: add test")
        result = SubjectPrefixChecker(required=[["ci", "cram"]])(commit)
        assert result.passed is True

    def test_subsequence_fails_when_only_first_token_present(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(subject="ci: add test")
        result = SubjectPrefixChecker(required=[["ci", "cram"]])(commit)
        assert result.passed is False

    def test_subsequence_matches_within_longer_chain(
        self, make_commit: MakeCommit
    ) -> None:
        # chain ["feat", "ci", "cram"] contains ["ci", "cram"] → PASS
        commit = make_commit(subject="feat: ci: cram: add test")
        result = SubjectPrefixChecker(required=[["ci", "cram"]])(commit)
        assert result.passed is True

    def test_case_insensitive(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="CI: add pipeline")
        result = SubjectPrefixChecker(required=[["ci"]])(commit)
        assert result.passed is True

    def test_no_prefix_with_required_fails(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="add feature without prefix")
        result = SubjectPrefixChecker(required=[["ci"]])(commit)
        assert result.passed is False

    def test_combined_with_whitelist_both_pass(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="ci: cram: add test")
        result = SubjectPrefixChecker(
            required=[["ci", "cram"]], whitelist=[["ci", "cram"]]
        )(commit)
        assert result.passed is True

    def test_combined_with_whitelist_required_not_satisfied(
        self, make_commit: MakeCommit
    ) -> None:
        # chain ["ci"] is in whitelist but doesn't match required ["ci", "cram"]
        commit = make_commit(subject="ci: add pipeline")
        result = SubjectPrefixChecker(
            required=[["ci", "cram"]], whitelist=[["ci", "cram"], ["ci"]]
        )(commit)
        assert result.passed is False


class TestSubjectPrefixNoChainHints:
    def test_no_hints_when_no_config(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="add feature without prefix")
        result = SubjectPrefixChecker()(commit)
        assert result.passed is False
        assert "expected one of" not in result.message

    def test_hints_from_required(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="add feature without prefix")
        result = SubjectPrefixChecker(required=[["ci"], ["cram"]])(commit)
        assert result.passed is False
        assert "ci:" in result.message
        assert "cram:" in result.message

    def test_hints_from_required_chain(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="add feature without prefix")
        result = SubjectPrefixChecker(required=[["ci", "cram"]])(commit)
        assert result.passed is False
        assert "ci: cram:" in result.message

    def test_hints_from_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="add feature without prefix")
        result = SubjectPrefixChecker(whitelist=[["feat"], ["fix"]])(commit)
        assert result.passed is False
        assert "feat:" in result.message
        assert "fix:" in result.message

    def test_no_whitelist_hints_in_blacklist_mode(
        self, make_commit: MakeCommit
    ) -> None:
        # blacklist mode: whitelist entries are irrelevant when no prefix found
        commit = make_commit(subject="add feature without prefix")
        result = SubjectPrefixChecker(
            blacklist=[["wip"]], whitelist=[["feat"]], mode="blacklist"
        )(commit)
        assert result.passed is False
        assert "feat:" not in result.message
