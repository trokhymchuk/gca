from datetime import datetime, timezone

import pytest

from git_commit_analyzer import (
    DirectoryModifiedFilter,
    FileModifiedFilter,
    GitCommit,
    GlobModifiedFilter,
    IsAmendFilter,
    IsFixupFilter,
    IsMergeFilter,
    IsRevertFilter,
    IsSquashFilter,
    NegatedFilter,
)

_NOW = datetime(2024, 1, 1, tzinfo=timezone.utc)


def make_commit(
    changed_files: list[str] | None = None,
    subject: str = "feat: test",
    parent_shas: list[str] | None = None,
) -> GitCommit:
    return GitCommit(
        sha="a" * 40,
        subject=subject,
        body="",
        description="",
        trailers=[],
        parent_shas=parent_shas or [],
        changed_files=changed_files or [],
        author_name="Test",
        author_email="test@example.com",
        author_date=_NOW,
        committer_name="Test",
        committer_email="test@example.com",
        committer_date=_NOW,
    )


# --- FileModifiedFilter ---

class TestFileModifiedFilter:
    def test_matches_exact_path(self):
        commit = make_commit(changed_files=["src/main.py"])
        assert FileModifiedFilter(files=["src/main.py"])(commit) is True

    def test_no_match_different_path(self):
        commit = make_commit(changed_files=["src/main.py"])
        assert FileModifiedFilter(files=["src/other.py"])(commit) is False

    def test_matches_any_of_list(self):
        commit = make_commit(changed_files=["a.py", "b.py"])
        assert FileModifiedFilter(files=["b.py", "c.py"])(commit) is True

    def test_no_match_none_in_list(self):
        commit = make_commit(changed_files=["a.py"])
        assert FileModifiedFilter(files=["c.py", "d.py"])(commit) is False

    def test_empty_files_never_matches(self):
        commit = make_commit(changed_files=["a.py"])
        assert FileModifiedFilter(files=[])(commit) is False

    def test_empty_changed_files_never_matches(self):
        commit = make_commit([])
        assert FileModifiedFilter(files=["a.py"])(commit) is False

    def test_name(self):
        assert FileModifiedFilter(files=[]).name == "file_modified"


# --- DirectoryModifiedFilter ---

class TestDirectoryModifiedFilter:
    def test_matches_direct_child(self):
        commit = make_commit(changed_files=["src/main.py"])
        assert DirectoryModifiedFilter(directories=["src"])(commit) is True

    def test_matches_nested(self):
        commit = make_commit(changed_files=["src/pkg/module.py"])
        assert DirectoryModifiedFilter(directories=["src/pkg"])(commit) is True

    def test_parent_dir_matches_nested_file(self):
        commit = make_commit(changed_files=["src/pkg/module.py"])
        assert DirectoryModifiedFilter(directories=["src"])(commit) is True

    def test_no_match_sibling_dir(self):
        commit = make_commit(changed_files=["src/main.py"])
        assert DirectoryModifiedFilter(directories=["tests"])(commit) is False

    def test_no_partial_name_match(self):
        # "sr" must not match "src/main.py"
        commit = make_commit(changed_files=["src/main.py"])
        assert DirectoryModifiedFilter(directories=["sr"])(commit) is False

    def test_trailing_slash_normalised(self):
        commit = make_commit(changed_files=["lib/util.py"])
        assert DirectoryModifiedFilter(directories=["lib/"])(commit) is True

    def test_matches_any_of_directories(self):
        commit = make_commit(changed_files=["docs/readme.md"])
        assert DirectoryModifiedFilter(directories=["src", "docs"])(commit) is True

    def test_empty_changed_files_never_matches(self):
        commit = make_commit([])
        assert DirectoryModifiedFilter(directories=["src"])(commit) is False

    def test_name(self):
        assert DirectoryModifiedFilter(directories=[]).name == "directory_modified"


# --- GlobModifiedFilter ---

class TestGlobModifiedFilter:
    def test_matches_star_extension(self):
        commit = make_commit(changed_files=["src/foo.py"])
        assert GlobModifiedFilter(patterns=["src/*.py"])(commit) is True

    def test_no_match_wrong_extension(self):
        commit = make_commit(changed_files=["src/foo.py"])
        assert GlobModifiedFilter(patterns=["src/*.ts"])(commit) is False

    def test_matches_double_star(self):
        commit = make_commit(changed_files=["a/b/c/foo.py"])
        assert GlobModifiedFilter(patterns=["**/*.py"])(commit) is True

    def test_matches_any_of_patterns(self):
        commit = make_commit(changed_files=["src/foo.ts"])
        assert GlobModifiedFilter(patterns=["*.md", "src/*.ts"])(commit) is True

    def test_no_match_none_of_patterns(self):
        commit = make_commit(changed_files=["src/foo.py"])
        assert GlobModifiedFilter(patterns=["*.md", "*.txt"])(commit) is False

    def test_empty_changed_files_never_matches(self):
        commit = make_commit([])
        assert GlobModifiedFilter(patterns=["*.py"])(commit) is False

    def test_name(self):
        assert GlobModifiedFilter(patterns=[]).name == "glob_modified"


# --- Commit property filters ---

class TestIsFixupFilter:
    def test_passes_for_fixup(self):
        assert IsFixupFilter()(make_commit(subject="fixup! feat: thing")) is True

    def test_passes_for_squash(self):
        assert IsFixupFilter()(make_commit(subject="squash! feat: thing")) is True

    def test_passes_for_amend(self):
        assert IsFixupFilter()(make_commit(subject="amend! feat: thing")) is True

    def test_fails_for_normal_commit(self):
        assert IsFixupFilter()(make_commit(subject="feat: thing")) is False

    def test_name(self):
        assert IsFixupFilter().name == "is_fixup"


class TestIsSquashFilter:
    def test_passes_for_squash(self):
        assert IsSquashFilter()(make_commit(subject="squash! feat: thing")) is True

    def test_fails_for_fixup(self):
        assert IsSquashFilter()(make_commit(subject="fixup! feat: thing")) is False

    def test_name(self):
        assert IsSquashFilter().name == "is_squash"


class TestIsAmendFilter:
    def test_passes_for_amend(self):
        assert IsAmendFilter()(make_commit(subject="amend! feat: thing")) is True

    def test_fails_for_fixup(self):
        assert IsAmendFilter()(make_commit(subject="fixup! feat: thing")) is False

    def test_name(self):
        assert IsAmendFilter().name == "is_amend"


class TestIsMergeFilter:
    def test_passes_for_merge(self):
        commit = make_commit(parent_shas=["aaa", "bbb"])
        assert IsMergeFilter()(commit) is True

    def test_fails_for_regular_commit(self):
        commit = make_commit(parent_shas=["aaa"])
        assert IsMergeFilter()(commit) is False

    def test_name(self):
        assert IsMergeFilter().name == "is_merge"


class TestIsRevertFilter:
    def test_passes_for_revert(self):
        commit = make_commit(subject='Revert "feat: add thing"')
        assert IsRevertFilter()(commit) is True

    def test_fails_for_normal_commit(self):
        assert IsRevertFilter()(make_commit(subject="feat: thing")) is False

    def test_name(self):
        assert IsRevertFilter().name == "is_revert"


# --- NegatedFilter ---

class TestNegatedFilter:
    def test_inverts_true_to_false(self):
        commit = make_commit(subject="fixup! feat: thing")
        assert NegatedFilter(inner=IsFixupFilter())(commit) is False

    def test_inverts_false_to_true(self):
        commit = make_commit(subject="feat: thing")
        assert NegatedFilter(inner=IsFixupFilter())(commit) is True

    def test_dynamic_name(self):
        assert NegatedFilter(inner=IsFixupFilter()).name == "not_is_fixup"

    def test_not_in_registry(self):
        from git_commit_analyzer.filters import CommitFilter
        assert "not_is_fixup" not in CommitFilter._registry

    def test_invert_flag_in_yaml(self, tmp_path):
        from pathlib import Path
        from git_commit_analyzer import load_ruleset
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: skip-merge-commits
    filters:
      - type: is_merge
        invert: true
    checkers:
      - type: subject_max_length
        max_length: 72
""")
        rf = load_ruleset(yaml_file)
        f = rf.ruleset.rules[0].filters[0]
        assert isinstance(f, NegatedFilter)
        assert f.name == "not_is_merge"

    def test_inverted_filter_skips_matching_commits(self, tmp_path):
        from pathlib import Path
        from git_commit_analyzer import load_ruleset
        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: no-fixup-rule
    filters:
      - type: is_fixup
        invert: true
    checkers:
      - type: subject_matches_regex
        pattern: "^feat: "
""")
        rf = load_ruleset(yaml_file)
        fixup = make_commit(subject="fixup! feat: thing")
        normal = make_commit(subject="bad subject")
        # fixup is filtered out (invert: true means is_fixup commits are excluded)
        assert rf.ruleset.check_commits([fixup]) == []
        # normal commit passes filter, fails checker
        assert len(rf.ruleset.check_commits([normal])) == 1
