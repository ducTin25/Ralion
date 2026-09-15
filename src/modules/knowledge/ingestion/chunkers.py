"""Category-profiled structural chunking for PROJECT Markdown documents."""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from functools import lru_cache

from markdown_it import MarkdownIt

from src.ai.retrieval_engine.chunking_config import load_chunking_config
from src.model.enums import DocumentCategory


@dataclass(frozen=True)
class ProjectChunk:
    content: str
    section_path: str
    token_count: int
    anchor: str


@dataclass(frozen=True)
class StructuralBlock:
    kind: str
    content: str


@dataclass(frozen=True)
class Section:
    path: str
    blocks: tuple[StructuralBlock, ...]


@dataclass(frozen=True)
class CategoryProfile:
    bonded_atomic_kinds: frozenset[str]
    refinement_strength: int = 1


_PROFILES = {
    DocumentCategory.OVERVIEW: CategoryProfile(frozenset()),
    DocumentCategory.ARCHITECTURE: CategoryProfile(frozenset(), refinement_strength=2),
    DocumentCategory.SETUP: CategoryProfile(frozenset({"list", "code"})),
    DocumentCategory.ACCESS_SECURITY: CategoryProfile(frozenset({"list", "table", "code"})),
    DocumentCategory.CODEBASE_GUIDE: CategoryProfile(frozenset({"code"})),
    DocumentCategory.CONVENTION: CategoryProfile(frozenset({"list", "table", "code"})),
    DocumentCategory.FIRST_TASK: CategoryProfile(frozenset({"list", "code"})),
}


def _token_count(text: str) -> int:
    try:
        import tiktoken

        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except (ImportError, OSError):
        return max(1, len(re.findall(r"\S+", text)))


@lru_cache(maxsize=1)
def _markdown_parser() -> MarkdownIt:
    return MarkdownIt("commonmark", {"html": False}).enable("table")


def _slug(value: str) -> str:
    value = re.sub(r"[^a-z0-9 _-]", "", value.lower().strip())
    return re.sub(r"[ _]+", "-", value).strip("-") or "document"


def _source_block(lines: list[str], token_map: list[int] | None) -> str:
    if token_map is None:
        return ""
    start, end = token_map
    return "\n".join(lines[start:end]).strip()


def parse_markdown_ast(markdown: str) -> list[Section]:
    """Parse Markdown AST tokens and retain source-faithful structural blocks."""
    lines = markdown.splitlines()
    tokens = _markdown_parser().parse(markdown)
    sections: list[Section] = []
    heading_stack: list[tuple[int, str]] = []
    current_path = "Document"
    current_blocks: list[StructuralBlock] = []
    consumed_until = -1

    def flush_section() -> None:
        if current_blocks:
            sections.append(Section(current_path, tuple(current_blocks)))
            current_blocks.clear()

    kind_for_type = {
        "paragraph_open": "paragraph",
        "bullet_list_open": "list",
        "ordered_list_open": "list",
        "table_open": "table",
        "fence": "code",
        "code_block": "code",
    }
    for index, token in enumerate(tokens):
        if token.type == "heading_open":
            flush_section()
            level = int(token.tag[1:])
            title = tokens[index + 1].content.strip()
            while heading_stack and heading_stack[-1][0] >= level:
                heading_stack.pop()
            heading_stack.append((level, title))
            current_path = " > ".join(item[1] for item in heading_stack)
            continue
        kind = kind_for_type.get(token.type)
        if kind is None or token.map is None or token.map[0] < consumed_until:
            continue
        content = _source_block(lines, token.map)
        if not content:
            continue
        current_blocks.append(StructuralBlock(kind, content))
        consumed_until = token.map[1]
    flush_section()
    return sections


def _profile(category: DocumentCategory) -> tuple[CategoryProfile, int, int, int]:
    params = load_chunking_config()["project_knowledge"]["rfc"]
    return (
        _PROFILES[category],
        int(params["target_size_tokens_min"]),
        int(params["target_size_tokens_max"]),
        int(params["hard_ceiling_tokens"]),
    )


def _bond_blocks(blocks: Iterable[StructuralBlock], profile: CategoryProfile) -> list[StructuralBlock]:
    """Keep explanatory paragraph + category-relevant atomic block together."""
    bonded: list[StructuralBlock] = []
    for block in blocks:
        if block.kind in profile.bonded_atomic_kinds and bonded and bonded[-1].kind == "paragraph":
            previous = bonded.pop()
            bonded.append(StructuralBlock(f"paragraph+{block.kind}", f"{previous.content}\n\n{block.content}"))
        else:
            bonded.append(block)
    return bonded


def _split_paragraph(text: str, ceiling: int, strength: int) -> list[StructuralBlock]:
    """Sentence-aware fallback used only by selective semantic refinement."""
    boundary = r"(?<=[.!?])\s+(?=(?:[A-Z0-9]|#{1,6}\s))"
    if strength > 1:
        boundary = r"(?<=[.!?;:])\s+(?=(?:[A-Z0-9]|[-*]|#{1,6}\s))"
    sentences = [part.strip() for part in re.split(boundary, text) if part.strip()]
    if len(sentences) <= 1:
        words = text.split()
        sentences = [" ".join(words[index : index + 180]) for index in range(0, len(words), 180)]
    result: list[StructuralBlock] = []
    current: list[str] = []
    for sentence in sentences:
        candidate = " ".join((*current, sentence))
        if current and _token_count(candidate) > ceiling:
            result.append(StructuralBlock("paragraph", " ".join(current)))
            current = [sentence]
        else:
            current.append(sentence)
    if current:
        result.append(StructuralBlock("paragraph", " ".join(current)))
    return result


def _refine_oversized(section: Section, blocks: list[StructuralBlock], ceiling: int, strength: int) -> list[StructuralBlock]:
    """Refine only oversized, heterogeneous sections; atomic blocks stay whole."""
    if _token_count("\n\n".join(block.content for block in blocks)) <= ceiling:
        return blocks
    kinds = {kind for block in blocks for kind in block.kind.split("+")}
    if len(kinds) < 2:
        return blocks
    refined: list[StructuralBlock] = []
    for block in blocks:
        if block.kind != "paragraph" or _token_count(block.content) <= ceiling:
            refined.append(block)
        else:
            refined.extend(_split_paragraph(block.content, ceiling, strength))
    return refined


def _emit_chunk(chunks: list[ProjectChunk], seen: dict[str, int], content: str, section_path: str) -> None:
    base = _slug(section_path)
    seen[base] = seen.get(base, 0) + 1
    suffix = "" if seen[base] == 1 else f"-{seen[base] - 1}"
    chunks.append(ProjectChunk(content, section_path, _token_count(content), f"{base}{suffix}"))


def chunk_markdown_document(markdown: str, *, title: str, document_category: DocumentCategory) -> list[ProjectChunk]:
    """AST → structure → category profile → packing → selective refinement."""
    profile, target_min, target_max, ceiling = _profile(document_category)
    del target_min  # Small atomic sections are source-faithful chunks; never pad them.
    chunks: list[ProjectChunk] = []
    seen: dict[str, int] = {}
    for section in parse_markdown_ast(markdown):
        blocks = _refine_oversized(section, _bond_blocks(section.blocks, profile), ceiling, profile.refinement_strength)
        packed: list[str] = []
        for block in blocks:
            candidate = "\n\n".join((*packed, block.content))
            if packed and _token_count(candidate) > target_max:
                _emit_chunk(chunks, seen, "\n\n".join(packed), section.path)
                packed = [block.content]
            else:
                packed.append(block.content)
        if packed:
            _emit_chunk(chunks, seen, "\n\n".join(packed), section.path)
    if not chunks and markdown.strip():
        _emit_chunk(chunks, seen, markdown.strip(), title)
    return chunks
