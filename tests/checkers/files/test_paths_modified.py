import pytest

from git_commit_analyzer import PathsModifiedChecker

from tests.checkers.conftest import MakeCommit


class TestPathsModifiedRequired:
    def test_passes_when_required_path_modified(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["db/migrations/001.sql"])
        result = PathsModifiedChecker(required=["db/migrations/"])(commit)
        assert result.passed is True

    def test_fails_when_required_path_missing(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        result = PathsModifiedChecker(required=["db/migrations/"])(commit)
        assert result.passed is False
        assert "db/migrations/" in result.message

    def test_passes_when_required_exact_file_modified(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["CHANGELOG.md", "src/main.py"])
        result = PathsModifiedChecker(required=["CHANGELOG.md"])(commit)
        assert result.passed is True

    def test_fails_when_required_exact_file_missing(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        result = PathsModifiedChecker(required=["CHANGELOG.md"])(commit)
        assert result.passed is False

    def test_multiple_required_all_must_be_present(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        result = PathsModifiedChecker(required=["src/main.py", "tests/"])(commit)
        assert result.passed is False
        assert "tests/" in result.message


class TestPathsModifiedWhitelistOnly:
    def test_passes_when_all_files_in_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["uv.lock", "pyproject.toml"])
        result = PathsModifiedChecker(
            whitelist=["uv.lock", "pyproject.toml", "package.json"]
        )(commit)
        assert result.passed is True

    def test_passes_when_files_under_whitelisted_directory(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["migrations/001.sql"])
        result = PathsModifiedChecker(whitelist=["migrations/"])(commit)
        assert result.passed is True

    def test_fails_when_file_outside_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["uv.lock", "src/secret.py"])
        result = PathsModifiedChecker(whitelist=["uv.lock"])(commit)
        assert result.passed is False
        assert "src/secret.py" in result.message

    def test_default_mode_is_whitelist_when_only_whitelist_set(self) -> None:
        checker = PathsModifiedChecker(whitelist=["known.txt"])
        assert checker._effective_mode() == "whitelist"

    def test_passes_with_no_changed_files(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=[])
        result = PathsModifiedChecker(whitelist=["a.py"])(commit)
        assert result.passed is True


class TestPathsModifiedBlacklistOnly:
    def test_passes_when_no_blacklisted_file_modified(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        result = PathsModifiedChecker(blacklist=[".env", "secrets/"])(commit)
        assert result.passed is True

    def test_fails_when_blacklisted_file_modified(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["src/main.py", ".env"])
        result = PathsModifiedChecker(blacklist=[".env"])(commit)
        assert result.passed is False
        assert ".env" in result.message

    def test_fails_when_file_under_blacklisted_directory(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["secrets/api_key.txt"])
        result = PathsModifiedChecker(blacklist=["secrets/"])(commit)
        assert result.passed is False
        assert "secrets/api_key.txt" in result.message

    def test_default_mode_is_blacklist_when_only_blacklist_set(self) -> None:
        checker = PathsModifiedChecker(blacklist=[".env"])
        assert checker._effective_mode() == "blacklist"

    def test_unlisted_files_are_allowed_in_blacklist_mode(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["src/main.py", "tests/test_a.py"])
        result = PathsModifiedChecker(blacklist=[".env"])(commit)
        assert result.passed is True


class TestPathsModifiedBothWithExplicitMode:
    def test_raises_when_both_set_without_mode(self) -> None:
        with pytest.raises(ValueError, match="mode"):
            PathsModifiedChecker(whitelist=["migrations/"], blacklist=[".env"])

    def test_mode_whitelist_enforces_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["migrations/001.sql", "unrelated.txt"])
        result = PathsModifiedChecker(
            whitelist=["migrations/"],
            blacklist=[".env"],
            mode="whitelist",
        )(commit)
        assert result.passed is False
        assert "unrelated.txt" in result.message

    def test_mode_whitelist_blacklist_still_forbidden(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["migrations/001.sql", ".env"])
        result = PathsModifiedChecker(
            whitelist=["migrations/"],
            blacklist=[".env"],
            mode="whitelist",
        )(commit)
        assert result.passed is False
        assert ".env" in result.message

    def test_mode_blacklist_allows_unlisted(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py", "docs/readme.md"])
        result = PathsModifiedChecker(
            whitelist=["src/"],
            blacklist=[".env"],
            mode="blacklist",
        )(commit)
        assert result.passed is True

    def test_mode_blacklist_blacklist_still_forbidden(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["src/main.py", ".env"])
        result = PathsModifiedChecker(
            whitelist=["src/"],
            blacklist=[".env"],
            mode="blacklist",
        )(commit)
        assert result.passed is False
        assert ".env" in result.message

    def test_invalid_mode_raises(self) -> None:
        with pytest.raises(ValueError, match="mode"):
            PathsModifiedChecker(mode="invalid")


class TestPathsModifiedCombined:
    def test_required_and_whitelist_together(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["db/migrations/001.sql", "src/models.py"])
        result = PathsModifiedChecker(
            required=["db/migrations/"],
            whitelist=["db/migrations/", "src/models.py"],
        )(commit)
        assert result.passed is True

    def test_required_missing_and_whitelist_violated(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        result = PathsModifiedChecker(
            required=["db/migrations/"],
            whitelist=["db/migrations/"],
        )(commit)
        assert result.passed is False
        assert "db/migrations/" in result.message
        assert "src/main.py" in result.message

    def test_empty_params_always_passes(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["anything.py"])
        result = PathsModifiedChecker()(commit)
        assert result.passed is True

    def test_name(self) -> None:
        assert PathsModifiedChecker().name == "paths_modified"
