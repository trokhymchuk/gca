import pytest

from git_commit_analyzer import IsolateChangesChecker

from tests.checkers.conftest import MakeCommit


GROUPS = [
    [".gitlab-ci.yml", ".gitlab/"],
    [".gitlab/", "profiles/"],
]


class TestIsolateChangesNoGroupTriggered:
    def test_passes_when_no_changed_files(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=[])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is True

    def test_passes_when_files_outside_all_groups(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["src/main.py", "tests/test_foo.py"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is True

    def test_passes_single_ungrouped_file(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["README.md"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is True


class TestIsolateChangesSingleGroupCovered:
    def test_passes_when_single_file_in_group_0(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=[".gitlab-ci.yml"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is True

    def test_passes_gitlab_dir_and_ci_yml_fit_group_0(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=[".gitlab-ci.yml", ".gitlab/pipeline.yml"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is True

    def test_passes_gitlab_dir_and_profiles_fit_group_1(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=[".gitlab/pipeline.yml", "profiles/dev.yml"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is True

    def test_passes_only_profiles_fits_group_1(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["profiles/prod.yml"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is True

    def test_passes_only_gitlab_dir_fits_both_groups(
        self, make_commit: MakeCommit
    ) -> None:
        # .gitlab/ belongs to both groups; fits in group 0 alone
        commit = make_commit(changed_files=[".gitlab/base.yml", ".gitlab/jobs.yml"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is True

    def test_passes_all_three_group_paths_fit_within_no_single_group(
        self, make_commit: MakeCommit
    ) -> None:
        # .gitlab-ci.yml (g0), profiles/ (g1): spans both → FAIL
        commit = make_commit(changed_files=[".gitlab-ci.yml", "profiles/dev.yml"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is False


class TestIsolateChangesViolations:
    def test_fails_when_gitlab_ci_and_profiles_modified(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=[".gitlab-ci.yml", "profiles/dev.yml"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is False

    def test_fails_when_ungrouped_file_mixed_with_group_member(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["src/main.py", ".gitlab/pipeline.yml"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is False
        assert "src/main.py" in result.message

    def test_fails_when_all_three_group_paths_modified(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            changed_files=[".gitlab-ci.yml", ".gitlab/jobs.yml", "profiles/dev.yml"]
        )
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is False

    def test_error_message_mentions_conflicting_files(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=[".gitlab-ci.yml", "profiles/dev.yml"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert ".gitlab-ci.yml" in result.message
        assert "profiles/dev.yml" in result.message


class TestIsolateChangesDirectoryPrefix:
    def test_directory_prefix_matches_nested_file(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=[".gitlab/tests/cram/test1.t"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is True

    def test_directory_prefix_does_not_match_sibling(
        self, make_commit: MakeCommit
    ) -> None:
        # .gitlabc/ should NOT match .gitlab/ prefix
        commit = make_commit(changed_files=[".gitlabc/file.yml"])
        result = IsolateChangesChecker(groups=GROUPS)(commit)
        assert result.passed is True  # not triggered → pass


class TestIsolateChangesBestMatch:
    """Verify that the most specific matching pattern wins across groups."""

    GROUPS_NESTED = [
        [".gitlab/", "abc/"],  # group 0: broad gitlab + abc
        [".gitlab/tests/cram/"],  # group 1: specific cram subdir
    ]

    def test_cram_file_alone_passes(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=[".gitlab/tests/cram/test1.t"])
        result = IsolateChangesChecker(groups=self.GROUPS_NESTED)(commit)
        assert result.passed is True

    def test_cram_file_with_abc_fails(self, make_commit: MakeCommit) -> None:
        # .gitlab/tests/cram/ best-matches group 1; abc/ belongs to group 0
        commit = make_commit(
            changed_files=[".gitlab/tests/cram/test1.t", "abc/config.yml"]
        )
        result = IsolateChangesChecker(groups=self.GROUPS_NESTED)(commit)
        assert result.passed is False

    def test_cram_file_with_other_gitlab_file_fails(
        self, make_commit: MakeCommit
    ) -> None:
        # .gitlab/tests/cram/test1.t: group1(.gitlab/tests/cram/ len19) > group0(.gitlab/ len8)
        #   → best group = {1}
        # .gitlab/pipeline.yml: group0(.gitlab/ len8), group1 no match (pipeline.yml ≠ cram)
        #   → best group = {0}
        # common = {} → FAIL (cram-specific change must not mix with broad gitlab change)
        commit = make_commit(
            changed_files=[
                ".gitlab/tests/cram/test1.t",
                ".gitlab/pipeline.yml",
            ]
        )
        result = IsolateChangesChecker(groups=self.GROUPS_NESTED)(commit)
        assert result.passed is False

    def test_gitlab_dir_and_abc_passes_via_group_0(
        self, make_commit: MakeCommit
    ) -> None:
        # .gitlab/pipeline.yml: group0(.gitlab/ len8) vs group1(.gitlab/tests/cram/ no match)
        # → only group 0 matches → group 0
        # abc/config.yml: group0(abc/ len4) → group 0
        # both group 0 → PASS
        commit = make_commit(changed_files=[".gitlab/pipeline.yml", "abc/config.yml"])
        result = IsolateChangesChecker(groups=self.GROUPS_NESTED)(commit)
        assert result.passed is True

    def test_cram_file_with_abc_error_message_mentions_both_files(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            changed_files=[".gitlab/tests/cram/test1.t", "abc/config.yml"]
        )
        result = IsolateChangesChecker(groups=self.GROUPS_NESTED)(commit)
        assert result.passed is False
        assert ".gitlab/tests/cram/test1.t" in result.message
        assert "abc/config.yml" in result.message

    def test_raises_when_groups_empty(self) -> None:
        with pytest.raises(ValueError, match="groups"):
            IsolateChangesChecker(groups=[])

    def test_raises_when_groups_not_provided(self) -> None:
        with pytest.raises((ValueError, TypeError)):
            IsolateChangesChecker()  # type: ignore[call-arg]
