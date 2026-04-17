from dataclasses import dataclass, field

from ..._prefix_utils import chain_matches, extract_prefixes_any
from ...models import GitCommit
from ..base import CommitFilter


# Example usage:
#
# rules:
#   # Apply description-length rule only to commits with a conventional prefix
#   - name: conventional-needs-description
#     filters:
#       - type: subject_prefix
#         any_of: [["feat"], ["fix"], ["refactor"]]
#     checkers:
#       - type: description_length
#         min: 20
#
#   # Commits with the 'ci: cram:' chain must have a sign-off
#   - name: cram-commits-need-signoff
#     filters:
#       - type: subject_prefix
#         any_of: [["ci", "cram"]]
#     checkers:
#       - type: trailer_present
#         required: ["Signed-off-by"]
@dataclass
class SubjectPrefixFilter(CommitFilter):
    """Passes based on the prefix chain of the commit subject.

    Each entry in ``any_of`` / ``all_of`` is an ordered list of prefix tokens
    representing a complete chain. For example ``["ci", "cram"]`` matches a
    subject starting with ``ci: cram: ``.

    Both conventional (``prefix(scope): ``) and non-conventional
    (``prefix: ``) segment formats are recognised when extracting the chain.

    Matching is exact and case-insensitive: the extracted chain must equal the
    pattern list element-by-element.

    The filter passes when:

    * ``any_of`` — the chain matches at least one listed pattern.
    * ``all_of`` — the chain matches every listed pattern.
    * Both — both conditions must hold.

    Attributes:
        any_of: Pass if the prefix chain matches any of these patterns.
        all_of: Pass if the prefix chain matches all of these patterns.
    """

    name = "subject_prefix"

    any_of: list[list[str]] = field(default_factory=list)
    all_of: list[list[str]] = field(default_factory=list)

    def __call__(self, commit: GitCommit) -> bool:
        """Return ``True`` when the commit's prefix chain satisfies the conditions.

        Args:
            commit: Commit whose subject is inspected.

        Returns:
            ``True`` when all configured conditions are met.
        """
        if not self.any_of and not self.all_of:
            return False

        chain = extract_prefixes_any(commit.subject)

        if self.any_of and not any(chain_matches(chain, p) for p in self.any_of):
            return False

        if self.all_of and not all(chain_matches(chain, p) for p in self.all_of):
            return False

        return True

    def __repr__(self) -> str:
        parts = []
        if self.any_of:
            parts.append(f"any_of={self.any_of!r}")
        if self.all_of:
            parts.append(f"all_of={self.all_of!r}")
        return f"SubjectPrefixFilter({', '.join(parts)})"
