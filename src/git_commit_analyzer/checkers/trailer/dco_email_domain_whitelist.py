import re
from dataclasses import dataclass, field

from ...models import GitCommit
from ..base import CheckResult, CommitChecker

_EMAIL_RE = re.compile(r"<([^>]+)>|(\S+@\S+)")


def _extract_email(value: str) -> str | None:
    """Return the email address from a trailer value, or None if not found."""
    m = _EMAIL_RE.search(value)
    if not m:
        return None
    return m.group(1) if m.group(1) else m.group(2)


def _domain(email: str) -> str:
    """Return the lowercased domain part of an email address."""
    return email.rsplit("@", 1)[-1].lower()


# Example usage:
#
# rules:
#   - name: dco-email-domain
#     checkers:
#       - type: dco_email_domain_whitelist
#         domains: ["example.com", "corp.org"]
#
#   # Custom DCO trailer name
#   - name: dco-email-domain-custom-trailer
#     checkers:
#       - type: dco_email_domain_whitelist
#         trailers: ["Co-authored-by"]
#         domains: ["example.com"]
@dataclass
class DcoEmailDomainWhitelistChecker(CommitChecker):
    """Validates that DCO trailer email addresses come from allowed domains.

    Inspects every value of each listed trailer and extracts the email address.
    The check fails if any email's domain is not in the ``domains`` whitelist, or
    if a trailer value contains no parseable email address.

    Trailers without any values are silently skipped (not treated as failures).

    Attributes:
        domains: Allowed email domains (case-insensitive).
        trailers: Trailer tokens to inspect.  Defaults to ``["Signed-off-by"]``.
    """

    name = "dco_email_domain_whitelist"

    domains: list[str]
    trailers: list[str] = field(default_factory=lambda: ["Signed-off-by"])

    def __post_init__(self) -> None:
        if not self.domains:
            raise ValueError("'domains' must not be empty")
        self._allowed = {d.lower() for d in self.domains}

    def _check_value(self, token: str, value: str) -> str | None:
        """Return an error string for this trailer value, or None if it passes."""
        email = _extract_email(value)
        if email is None:
            return (
                f"Trailer '{token}' value {value!r} contains no parseable email address"
            )
        domain = _domain(email)
        if domain not in self._allowed:
            return (
                f"Trailer '{token}' email '{email}' has domain '{domain}' "
                f"which is not in the allowed domains: {sorted(self._allowed)}"
            )
        return None

    def __call__(self, commit: GitCommit) -> CheckResult:
        """Check that all DCO trailer emails come from whitelisted domains.

        Args:
            commit: Commit whose trailers are inspected.

        Returns:
            A :class:`CheckResult` describing whether the commit passed or failed.
        """
        errors: list[str] = []
        for token in self.trailers:
            for value in commit.trailer(token):
                if err := self._check_value(token, value):
                    errors.append(err)
        if errors:
            return CheckResult.fail("; ".join(errors))
        return CheckResult.ok("All DCO email domains are allowed")

    def __repr__(self) -> str:
        return (
            f"DcoEmailDomainWhitelistChecker("
            f"trailers={self.trailers!r}, domains={self.domains!r})"
        )
