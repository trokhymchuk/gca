"""Shared prefix-extraction utilities used by the subject_prefix checker and filter."""

from __future__ import annotations

import re

# Matches a single non-conventional segment: 'prefix: '
_SEGMENT_RE = re.compile(r"^([A-Za-z0-9_-]+): ")
# Matches a single conventional segment: 'prefix(scope): '
_SEGMENT_CONVENTIONAL_RE = re.compile(r"^([A-Za-z0-9_-]+)\(.+?\): ")
# Matches either format — used by the filter which doesn't enforce one style.
_SEGMENT_ANY_RE = re.compile(r"^([A-Za-z0-9_-]+)(?:\(.+?\))?: ")


def extract_prefixes(subject: str, *, conventional: bool = False) -> list[str]:
    """Extract all leading prefix segments from *subject*.

    Args:
        subject: The commit subject line.
        conventional: When ``True`` each segment must be in
            ``prefix(scope): `` form; when ``False`` the plain
            ``prefix: `` form is expected.

    Returns:
        Ordered list of prefix tokens, e.g. ``["ci", "cram"]`` for
        ``"ci: cram: add test"``.
    """
    pattern = _SEGMENT_CONVENTIONAL_RE if conventional else _SEGMENT_RE
    prefixes: list[str] = []
    remaining = subject
    while True:
        m = pattern.match(remaining)
        if not m:
            break
        prefixes.append(m.group(1))
        remaining = remaining[m.end() :]
    return prefixes


def extract_prefixes_any(subject: str) -> list[str]:
    """Extract prefixes accepting both conventional and non-conventional segments."""
    prefixes: list[str] = []
    remaining = subject
    while True:
        m = _SEGMENT_ANY_RE.match(remaining)
        if not m:
            break
        prefixes.append(m.group(1))
        remaining = remaining[m.end() :]
    return prefixes


def chain_matches(chain: list[str], pattern: list[str]) -> bool:
    """Return ``True`` when *chain* equals *pattern* (case-insensitive)."""
    if len(chain) != len(pattern):
        return False
    return all(c.lower() == p.lower() for c, p in zip(chain, pattern))
