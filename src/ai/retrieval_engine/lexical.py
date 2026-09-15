"""Deterministic lexical fields shared by every ingestion path."""

from __future__ import annotations

import re

# IDs and symbols benefit from a literal BM25 field.  This intentionally does
# not attempt language stemming or transliteration; those are index settings.
# Letter classes use `[^\W\d_]` (any Unicode letter, digits/underscore excluded) rather than
# `[A-Za-z]` so an identifier-shaped token written in Vietnamese script (e.g. a hyphenated
# document code or clause reference) is still extracted -- an ASCII-only class produced an
# empty identifier set for such tokens regardless of the query's language bucket.
_IDENTIFIER = re.compile(
    r"\b(?:[^\W\d_]+(?:[-_][^\W_]+)+|[^\W\d_]{2,}\d+|RFC\s+\d+|\d+(?:\.\d+)+)\b",
    re.IGNORECASE,
)


def lexical_identifiers(text: str) -> str:
    """Return stable, newline-separated identifier tokens for ParadeDB."""
    seen: set[str] = set()
    identifiers: list[str] = []
    for match in _IDENTIFIER.finditer(text):
        value = match.group(0).strip()
        key = value.casefold()
        if key and key not in seen:
            seen.add(key)
            identifiers.append(value)
    return "\n".join(identifiers)
