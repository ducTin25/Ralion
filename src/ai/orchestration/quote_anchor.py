"""Linear, source-owned quote anchor verification.

The normalized representation deliberately retains punctuation.  It is only
whitespace-, case-, NFC-, and configured-zero-width tolerant.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

_TOKENS = re.compile(r"\S+")
_ZERO_WIDTH = "\u200b\u200c\u200d\u2060\ufeff"
_ZERO_WIDTH_TABLE = str.maketrans("", "", _ZERO_WIDTH)


def fold(value: str) -> str:
    """Return the shared normalized form used for source and model quotes."""
    tokens = (
        unicodedata.normalize("NFC", match.group(0)).translate(_ZERO_WIDTH_TABLE).casefold()
        for match in _TOKENS.finditer(value)
    )
    return " ".join(token for token in tokens if token)


@dataclass(frozen=True)
class QuoteAnchorIndex:
    """Normalized tokens plus boundaries mapped back to the original content."""

    content: str
    normalized_content: str
    token_starts: frozenset[int]
    token_ends: frozenset[int]
    source_starts: dict[int, int]
    source_ends: dict[int, int]


def build_index(content: str) -> QuoteAnchorIndex:
    """Normalize source content once and retain offsets into its exact text."""
    normalized_tokens: list[str] = []
    source_spans: list[tuple[int, int]] = []
    for match in _TOKENS.finditer(content):
        token = unicodedata.normalize("NFC", match.group(0)).translate(_ZERO_WIDTH_TABLE).casefold()
        if token:
            normalized_tokens.append(token)
            source_spans.append(match.span())

    starts: set[int] = set()
    ends: set[int] = set()
    source_starts: dict[int, int] = {}
    source_ends: dict[int, int] = {}
    position = 0
    for token, (source_start, source_end) in zip(normalized_tokens, source_spans, strict=True):
        start = position
        end = start + len(token)
        starts.add(start)
        ends.add(end)
        source_starts[start] = source_start
        source_ends[end] = source_end
        # POL-010 (2026-08-30): the source frequently glues a trailing separator straight onto
        # the last word of a clause with no space -- "...làm việc**, ghi rõ..." -- while a
        # legitimate model quote correctly stops before the separator. Without this, an exact,
        # faithful quote is rejected because its end lands *inside* that fused token instead of
        # on a registered boundary. Register one extra end boundary at the point where the raw
        # token's own trailing separator run starts, mapped back to that exact source offset, so
        # a quote ending there is recognized. This only ever shortens what a quote may stop at
        # (never extends a token, never accepts a mid-word cut) -- see `_ATTACHED_PUNCTUATION`.
        raw_token = content[source_start:source_end]
        raw_trimmed = raw_token.rstrip(_ATTACHED_PUNCTUATION)
        if raw_trimmed and raw_trimmed != raw_token:
            trimmed_source_end = source_start + len(raw_trimmed)
            trimmed_token = (
                unicodedata.normalize("NFC", raw_trimmed).translate(_ZERO_WIDTH_TABLE).casefold()
            )
            trimmed_end = start + len(trimmed_token)
            if trimmed_token and trimmed_end != end:
                ends.add(trimmed_end)
                source_ends.setdefault(trimmed_end, trimmed_source_end)
        position = end + 1

    return QuoteAnchorIndex(
        content=content,
        normalized_content=" ".join(normalized_tokens),
        token_starts=frozenset(starts),
        token_ends=frozenset(ends),
        source_starts=source_starts,
        source_ends=source_ends,
    )


_TERMINAL_PUNCTUATION = ".!?;:"

# Trailing punctuation a source token may carry with no preceding space, where a quote correctly
# stopping just before it is still an exact, unambiguous substring of the source word. Deliberately
# narrow -- no brackets/quotes that could plausibly be semantically load-bearing at a clause
# boundary -- so this never tolerates a mid-word cut or a real wording difference.
_ATTACHED_PUNCTUATION = ",.;:!?"


def _first_token_boundary_match(index: QuoteAnchorIndex, needle: str) -> str | None:
    position = index.normalized_content.find(needle)
    while position != -1:
        end = position + len(needle)
        if position in index.token_starts and end in index.token_ends:
            return index.content[index.source_starts[position] : index.source_ends[end]]
        position = index.normalized_content.find(needle, position + 1)
    return None


def find_source_span(index: QuoteAnchorIndex, quote: str) -> str | None:
    """Return the first token-boundary quote occurrence as an exact source slice.

    Tolerates the model appending extra terminal punctuation to an otherwise exact quote (a
    common completion artifact): progressively strips trailing `.!?;:` from the quote and retries,
    still requiring an exact token-boundary match against the source. Semantic edits or
    punctuation changes elsewhere in the quote are never tolerated.
    """
    variants = [quote]
    trimmed = quote.rstrip()
    while trimmed and trimmed[-1] in _TERMINAL_PUNCTUATION:
        trimmed = trimmed[:-1].rstrip()
        if trimmed:
            variants.append(trimmed)

    for variant in variants:
        needle = fold(variant)
        if not needle:
            continue
        match = _first_token_boundary_match(index, needle)
        if match is not None:
            return match
    return None
