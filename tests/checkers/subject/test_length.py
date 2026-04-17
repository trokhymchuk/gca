from git_commit_analyzer import SubjectLengthChecker

from tests.checkers.conftest import MakeCommit


class TestSubjectLengthMin:
    def test_passes_when_above_min(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: a solid subject line")
        result = SubjectLengthChecker(min=10)(commit)
        assert result.passed is True

    def test_passes_when_exactly_min(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="1234567890")
        result = SubjectLengthChecker(min=10)(commit)
        assert result.passed is True

    def test_fails_when_below_min(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="short")
        result = SubjectLengthChecker(min=10)(commit)
        assert result.passed is False
        assert "below minimum" in result.message


class TestSubjectLengthMax:
    def test_passes_when_below_max(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: short")
        result = SubjectLengthChecker(max=72)(commit)
        assert result.passed is True

    def test_passes_when_exactly_max(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="x" * 72)
        result = SubjectLengthChecker(max=72)(commit)
        assert result.passed is True

    def test_fails_when_above_max(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="x" * 73)
        result = SubjectLengthChecker(max=72)(commit)
        assert result.passed is False
        assert "exceeds maximum" in result.message


class TestSubjectLengthBoth:
    def test_passes_when_within_bounds(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="feat: add feature")
        result = SubjectLengthChecker(min=10, max=72)(commit)
        assert result.passed is True

    def test_fails_min_violation(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="short")
        result = SubjectLengthChecker(min=10, max=72)(commit)
        assert result.passed is False
        assert "below minimum" in result.message

    def test_fails_max_violation(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="x" * 100)
        result = SubjectLengthChecker(min=10, max=72)(commit)
        assert result.passed is False
        assert "exceeds maximum" in result.message

    def test_no_params_always_passes(self, make_commit: MakeCommit) -> None:
        commit = make_commit(subject="anything")
        result = SubjectLengthChecker()(commit)
        assert result.passed is True

    def test_name(self) -> None:
        assert SubjectLengthChecker().name == "subject_length"
