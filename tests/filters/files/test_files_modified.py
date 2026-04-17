from git_commit_analyzer import PathsModifiedFilter

from tests.filters.conftest import MakeCommit


class TestPathsModifiedFilterAnyOf:
    def test_matches_exact_file(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        assert PathsModifiedFilter(any_of=["src/main.py"])(commit) is True

    def test_no_match_different_file(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        assert PathsModifiedFilter(any_of=["src/other.py"])(commit) is False

    def test_matches_any_of_files(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["a.py", "b.py"])
        assert PathsModifiedFilter(any_of=["b.py", "c.py"])(commit) is True

    def test_matches_directory_prefix(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        assert PathsModifiedFilter(any_of=["src/"])(commit) is True

    def test_matches_nested_directory(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/pkg/module.py"])
        assert PathsModifiedFilter(any_of=["src/"])(commit) is True

    def test_no_match_sibling_directory(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        assert PathsModifiedFilter(any_of=["tests/"])(commit) is False

    def test_no_partial_name_match(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        assert PathsModifiedFilter(any_of=["sr/"])(commit) is False

    def test_matches_glob_extension(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/foo.py"])
        assert PathsModifiedFilter(any_of=["src/*.py"])(commit) is True

    def test_no_match_glob_wrong_extension(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/foo.py"])
        assert PathsModifiedFilter(any_of=["src/*.ts"])(commit) is False

    def test_matches_double_star_glob(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["a/b/c/foo.py"])
        assert PathsModifiedFilter(any_of=["**/*.py"])(commit) is True

    def test_mixed_files_and_directories(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["config.yml"])
        assert PathsModifiedFilter(any_of=["config.yml", "src/"])(commit) is True

    def test_mixed_directory_and_glob(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["lib/util.py"])
        assert PathsModifiedFilter(any_of=["src/", "lib/*.py"])(commit) is True


class TestPathsModifiedFilterAllOf:
    def test_all_present_passes(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py", "tests/test_main.py"])
        assert (
            PathsModifiedFilter(all_of=["src/main.py", "tests/test_main.py"])(commit)
            is True
        )

    def test_missing_one_fails(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        assert (
            PathsModifiedFilter(all_of=["src/main.py", "tests/test_main.py"])(commit)
            is False
        )

    def test_directory_all_of(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/a.py", "tests/b.py"])
        assert PathsModifiedFilter(all_of=["src/", "tests/"])(commit) is True

    def test_directory_all_of_missing(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/a.py"])
        assert PathsModifiedFilter(all_of=["src/", "tests/"])(commit) is False

    def test_glob_all_of(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/a.py", "docs/readme.md"])
        assert PathsModifiedFilter(all_of=["src/*.py", "docs/*.md"])(commit) is True

    def test_glob_all_of_missing(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/a.py"])
        assert PathsModifiedFilter(all_of=["src/*.py", "docs/*.md"])(commit) is False


class TestPathsModifiedFilterCombined:
    def test_both_conditions_met(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py", "tests/test_main.py"])
        assert (
            PathsModifiedFilter(
                any_of=["src/"],
                all_of=["src/main.py", "tests/test_main.py"],
            )(commit)
            is True
        )

    def test_any_of_fails_with_all_of(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["docs/readme.md", "tests/test_main.py"])
        assert (
            PathsModifiedFilter(
                any_of=["src/"],
                all_of=["docs/readme.md", "tests/test_main.py"],
            )(commit)
            is False
        )

    def test_all_of_fails_with_any_of(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["src/main.py"])
        assert (
            PathsModifiedFilter(
                any_of=["src/"],
                all_of=["src/main.py", "tests/test_main.py"],
            )(commit)
            is False
        )

    def test_empty_params_never_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit(changed_files=["a.py"])
        assert PathsModifiedFilter()(commit) is False

    def test_empty_changed_files_never_matches(self, make_commit: MakeCommit) -> None:
        commit = make_commit([])
        assert PathsModifiedFilter(any_of=["a.py"])(commit) is False

    def test_name(self) -> None:
        assert PathsModifiedFilter().name == "paths_modified"
