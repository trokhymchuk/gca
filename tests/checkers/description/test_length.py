from git_commit_analyzer import DescriptionLengthChecker

from tests.checkers.conftest import MakeCommit


class TestDescriptionLengthMin:
    def test_passes_when_above_min(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="A detailed description of changes made.")
        result = DescriptionLengthChecker(min=20)(commit)
        assert result.passed is True

    def test_passes_when_exactly_min(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="x" * 20)
        result = DescriptionLengthChecker(min=20)(commit)
        assert result.passed is True

    def test_fails_when_below_min(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="short")
        result = DescriptionLengthChecker(min=20)(commit)
        assert result.passed is False
        assert "below minimum" in result.message

    def test_fails_when_empty_description(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="")
        result = DescriptionLengthChecker(min=20)(commit)
        assert result.passed is False


class TestDescriptionLengthLineMax:
    def test_passes_when_all_lines_within_limit(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="Short line\nAnother short line")
        result = DescriptionLengthChecker(line_max=100)(commit)
        assert result.passed is True

    def test_passes_when_empty_description(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="")
        result = DescriptionLengthChecker(line_max=100)(commit)
        assert result.passed is True

    def test_fails_when_line_exceeds_max(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="x" * 101)
        result = DescriptionLengthChecker(line_max=100)(commit)
        assert result.passed is False
        assert "Line 1" in result.message
        assert "exceeds maximum" in result.message

    def test_reports_first_offending_line(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="ok\n" + "y" * 101 + "\nok")
        result = DescriptionLengthChecker(line_max=100)(commit)
        assert result.passed is False
        assert "Line 2" in result.message


class TestDescriptionLengthBoth:
    def test_passes_both_constraints(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="A good description here\nSecond line.")
        result = DescriptionLengthChecker(min=20, line_max=100)(commit)
        assert result.passed is True

    def test_fails_min_only(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="short")
        result = DescriptionLengthChecker(min=20, line_max=100)(commit)
        assert result.passed is False
        assert "below minimum" in result.message

    def test_fails_line_max_only(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="x" * 101)
        result = DescriptionLengthChecker(min=5, line_max=100)(commit)
        assert result.passed is False
        assert "exceeds maximum" in result.message

    def test_no_params_always_passes(self, make_commit: MakeCommit) -> None:
        commit = make_commit(description="anything")
        result = DescriptionLengthChecker()(commit)
        assert result.passed is True

    def test_name(self) -> None:
        assert DescriptionLengthChecker().name == "description_length"
