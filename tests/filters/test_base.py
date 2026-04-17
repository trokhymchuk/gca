from git_commit_analyzer import CommitTypeFilter, NegatedFilter

from tests.filters.conftest import MakeCommit


class TestNegatedFilter:
    def test_inverts_true_to_false(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="fixup! feat: thing")
        assert NegatedFilter(inner=CommitTypeFilter(types=["fixup"]))(commit) is False

    def test_inverts_false_to_true(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: thing")
        assert NegatedFilter(inner=CommitTypeFilter(types=["fixup"]))(commit) is True

    def test_dynamic_name(self) -> None:
        assert (
            NegatedFilter(inner=CommitTypeFilter(types=["fixup"])).name
            == "not_commit_type"
        )

    def test_not_in_registry(self) -> None:
        from git_commit_analyzer.filters import CommitFilter

        assert "not_commit_type" not in CommitFilter._registry

    def test_invert_flag_in_yaml(self, tmp_path, make_commit: MakeCommit) -> None:
        from git_commit_analyzer import load_config

        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: skip-merge-commits
    filters:
      - type: commit_type
        types: ["merge"]
        invert: true
    checkers:
      - type: subject_length
        max: 72
""")
        rf = load_config(yaml_file)
        f = rf.ruleset.rules[0].filters[0]
        assert isinstance(f, NegatedFilter)
        assert f.name == "not_commit_type"

    def test_inverted_filter_skips_matching_commits(
        self, tmp_path, make_commit: MakeCommit
    ) -> None:
        from git_commit_analyzer import load_config

        yaml_file = tmp_path / "rules.yml"
        yaml_file.write_text("""
rules:
  - name: no-fixup-rule
    filters:
      - type: commit_type
        types: ["fixup"]
        invert: true
    checkers:
      - type: subject_matches_regex
        pattern: "^feat: "
""")
        rf = load_config(yaml_file)
        fixup = make_commit(subject="fixup! feat: thing")
        normal = make_commit(subject="bad subject")
        assert rf.ruleset.check_commits([fixup]) == []
        assert len(rf.ruleset.check_commits([normal])) == 1
