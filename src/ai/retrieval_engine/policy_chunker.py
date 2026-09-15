"""Heading-aware chunking for company policy Markdown documents."""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass

from src.ai.retrieval_engine.chunking_config import policy_params


@dataclass(frozen=True)
class PolicyChunk:
    content: str
    heading_path: str
    token_count: int
    is_atomic: bool = False


def _default_token_count(text: str) -> int:
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except (ImportError, OSError):
        return max(1, len(re.findall(r"\S+", text)))


def _sections(markdown: str) -> list[tuple[str, list[str]]]:
    sections: list[tuple[str, list[str]]] = []
    current_heading = "Document"
    current_lines: list[str] = []
    for line in markdown.splitlines():
        match = re.match(r"^(#{2,3})\s+(.+?)\s*$", line)
        if match:
            if current_lines and current_heading != "Document":
                sections.append((current_heading, current_lines))
            current_heading = match.group(2)
            current_lines = []
        else:
            current_lines.append(line)
    if current_lines and current_heading != "Document":
        sections.append((current_heading, current_lines))
    return sections


def _is_table(line: str) -> bool:
    return line.strip().startswith("|")


def _is_numbered(line: str) -> bool:
    return bool(re.match(r"^\s*\d+[.)]\s+", line))


def _atomic_blocks(lines: list[str]) -> tuple[list[tuple[int, list[str]]], set[int]]:
    """Return atomic blocks and line indexes consumed by those blocks."""
    blocks: list[tuple[int, list[str]]] = []
    consumed: set[int] = set()
    i = 0
    while i < len(lines):
        if not lines[i].strip():
            i += 1
            continue
        if _is_table(lines[i]):
            start = i
            while i < len(lines) and (_is_table(lines[i]) or not lines[i].strip()):
                if lines[i].strip():
                    consumed.add(i)
                i += 1
            blocks.append((start, [line for line in lines[start:i] if line.strip()]))
            continue
        if _is_numbered(lines[i]):
            start = i
            while i < len(lines) and (_is_numbered(lines[i]) or lines[i].startswith(("  ", "\t"))):
                consumed.add(i)
                i += 1
            blocks.append((start, [line for line in lines[start:i] if line.strip()]))
            continue
        i += 1
    return blocks, consumed


def chunk_policy_markdown(
    markdown: str,
    *,
    document_code: str,
    purpose_sentence: str = "",
    config: dict | None = None,
    token_count: Callable[[str], int] = _default_token_count,
) -> list[PolicyChunk]:
    """Chunk policy content while preserving tables and numbered procedures."""
    params = policy_params(config)
    target_min = int(params["target_size_tokens_min"])
    target_max = int(params["target_size_tokens_max"])
    ceiling = int(params["hard_ceiling_tokens"])
    overlap_min = int(params["force_split_overlap_tokens_min"])
    overlap_max = int(params["force_split_overlap_tokens_max"])
    positioned_chunks: list[tuple[tuple[int, int], PolicyChunk]] = []

    for section_index, (heading, lines) in enumerate(_sections(markdown)):
        atomic, consumed = _atomic_blocks(lines)
        for block_start, block in atomic:
            text = "\n".join(block).strip()
            positioned_chunks.append(
                ((section_index, block_start), PolicyChunk(text, heading, token_count(text), True))
            )

        paragraphs: list[tuple[int, str]] = []
        current: list[str] = []
        current_start = 0
        for index, line in enumerate(lines):
            if index in consumed:
                if current:
                    paragraphs.append((current_start, "\n".join(current).strip()))
                    current = []
                continue
            if line.strip():
                if not current:
                    current_start = index
                current.append(line)
            elif current:
                paragraphs.append((current_start, "\n".join(current).strip()))
                current = []
        if current:
            paragraphs.append((current_start, "\n".join(current).strip()))

        packed: list[str] = []
        packed_tokens = 0
        packed_start = 0
        for paragraph_start, paragraph in paragraphs:
            paragraph_tokens = token_count(paragraph)
            if paragraph_tokens > ceiling:
                if packed:
                    positioned_chunks.append(
                        ((section_index, packed_start), PolicyChunk("\n\n".join(packed), heading, packed_tokens))
                    )
                    packed, packed_tokens = [], 0
                words = paragraph.split()
                start = 0
                while start < len(words):
                    end = start
                    while end < len(words) and token_count(" ".join(words[start : end + 1])) <= ceiling:
                        end += 1
                    piece = " ".join(words[start:end])
                    if not piece:
                        raise ValueError("Unable to split oversized policy paragraph")
                    positioned_chunks.append(
                        ((section_index, paragraph_start + start), PolicyChunk(piece, heading, token_count(piece)))
                    )
                    if end == len(words):
                        break
                    overlap = max(overlap_min, min(overlap_max, 20))
                    start = max(start + 1, end - overlap)
                continue
            if packed and packed_tokens + paragraph_tokens > target_max:
                positioned_chunks.append(
                    ((section_index, packed_start), PolicyChunk("\n\n".join(packed), heading, packed_tokens))
                )
                packed, packed_tokens = [], 0
            if not packed:
                packed_start = paragraph_start
            packed.append(paragraph)
            packed_tokens += paragraph_tokens
            if packed_tokens >= target_min:
                positioned_chunks.append(
                    ((section_index, packed_start), PolicyChunk("\n\n".join(packed), heading, packed_tokens))
                )
                packed, packed_tokens = [], 0
        if packed:
            positioned_chunks.append(
                ((section_index, packed_start), PolicyChunk("\n\n".join(packed), heading, packed_tokens))
            )

    # Add context only to the derived embedding text; display content remains source-faithful.
    positioned_chunks.sort(key=lambda item: item[0])
    return [chunk for _, chunk in positioned_chunks]


def embedding_text_for_policy_chunk(
    chunk: PolicyChunk, *, document_code: str, purpose_sentence: str = ""
) -> str:
    prefix = " › ".join(part for part in (document_code, chunk.heading_path) if part)
    if purpose_sentence:
        prefix = f"{prefix} — {purpose_sentence}"
    return f"{prefix}\n\n{chunk.content}" if prefix else chunk.content
