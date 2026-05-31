import pytest

from git_commit_analyzer import DcoEmailDomainWhitelistChecker, Trailer

from tests.checkers.conftest import MakeCommit


class TestDcoEmailDomainWhitelistCheckerPasses:
    def test_passes_when_no_trailers_present(self, make_commit: MakeCommit) -> None:
        commit = make_commit()
        result = DcoEmailDomainWhitelistChecker(domains=["example.com"])(commit)
        assert result.passed is True

    def test_passes_with_angle_bracket_email(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[Trailer("Signed-off-by", "Alice <alice@example.com>")]
        )
        result = DcoEmailDomainWhitelistChecker(domains=["example.com"])(commit)
        assert result.passed is True

    def test_passes_with_bare_email(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "alice@example.com")])
        result = DcoEmailDomainWhitelistChecker(domains=["example.com"])(commit)
        assert result.passed is True

    def test_domain_match_is_case_insensitive(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[Trailer("Signed-off-by", "Alice <alice@EXAMPLE.COM>")]
        )
        result = DcoEmailDomainWhitelistChecker(domains=["example.com"])(commit)
        assert result.passed is True

    def test_allowed_domain_config_is_case_insensitive(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[Trailer("Signed-off-by", "Alice <alice@example.com>")]
        )
        result = DcoEmailDomainWhitelistChecker(domains=["EXAMPLE.COM"])(commit)
        assert result.passed is True

    def test_passes_when_multiple_trailers_all_allowed(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Signed-off-by", "Alice <alice@example.com>"),
                Trailer("Signed-off-by", "Bob <bob@corp.org>"),
            ]
        )
        result = DcoEmailDomainWhitelistChecker(domains=["example.com", "corp.org"])(
            commit
        )
        assert result.passed is True

    def test_passes_with_custom_trailer(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[Trailer("Co-authored-by", "Dev <dev@example.com>")]
        )
        result = DcoEmailDomainWhitelistChecker(
            trailers=["Co-authored-by"], domains=["example.com"]
        )(commit)
        assert result.passed is True

    def test_ignores_unconfigured_trailer(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Dev <dev@other.com>")])
        result = DcoEmailDomainWhitelistChecker(
            trailers=["Co-authored-by"], domains=["example.com"]
        )(commit)
        assert result.passed is True


class TestDcoEmailDomainWhitelistCheckerFails:
    def test_fails_when_domain_not_in_whitelist(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Eve <eve@evil.com>")])
        result = DcoEmailDomainWhitelistChecker(domains=["example.com"])(commit)
        assert result.passed is False
        assert "evil.com" in result.message
        assert "example.com" in result.message

    def test_fails_when_no_email_in_value(self, make_commit: MakeCommit) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Just a name")])
        result = DcoEmailDomainWhitelistChecker(domains=["example.com"])(commit)
        assert result.passed is False
        assert "no parseable email" in result.message

    def test_fails_when_one_of_multiple_trailers_has_bad_domain(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Signed-off-by", "Alice <alice@example.com>"),
                Trailer("Signed-off-by", "Eve <eve@evil.com>"),
            ]
        )
        result = DcoEmailDomainWhitelistChecker(domains=["example.com"])(commit)
        assert result.passed is False
        assert "evil.com" in result.message

    def test_error_message_includes_trailer_token(
        self, make_commit: MakeCommit
    ) -> None:
        commit = make_commit(trailers=[Trailer("Signed-off-by", "Eve <eve@evil.com>")])
        result = DcoEmailDomainWhitelistChecker(domains=["example.com"])(commit)
        assert "Signed-off-by" in result.message

    def test_fails_on_multiple_errors_combined(self, make_commit: MakeCommit) -> None:
        commit = make_commit(
            trailers=[
                Trailer("Signed-off-by", "Eve <eve@evil.com>"),
                Trailer("Signed-off-by", "Mal <mal@bad.io>"),
            ]
        )
        result = DcoEmailDomainWhitelistChecker(domains=["example.com"])(commit)
        assert result.passed is False
        assert "evil.com" in result.message
        assert "bad.io" in result.message


class TestDcoEmailDomainWhitelistCheckerValidation:
    def test_empty_domains_raises(self) -> None:
        with pytest.raises(ValueError, match="domains"):
            DcoEmailDomainWhitelistChecker(domains=[])

    def test_name(self) -> None:
        assert (
            DcoEmailDomainWhitelistChecker(domains=["example.com"]).name
            == "dco_email_domain_whitelist"
        )

    def test_default_trailers(self) -> None:
        checker = DcoEmailDomainWhitelistChecker(domains=["example.com"])
        assert checker.trailers == ["Signed-off-by"]

    def test_repr_includes_domains_and_trailers(self) -> None:
        checker = DcoEmailDomainWhitelistChecker(domains=["example.com"])
        r = repr(checker)
        assert "example.com" in r
        assert "Signed-off-by" in r
