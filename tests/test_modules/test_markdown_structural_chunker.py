import pytest

from src.core.security.secret_scan import scan as secret_scan_and_redact
from src.model.enums import DocumentCategory
from src.modules.knowledge.ingestion.chunkers import (
    _PROFILES,
    StructuralBlock,
    _bond_blocks,
    chunk_markdown_document,
    parse_markdown_ast,
)


def test_ast_parser_builds_heading_hierarchy() -> None:
    sections = parse_markdown_ast("# Service\nIntro.\n\n## Setup\nRun it.\n\n### Local\nUse Docker.")
    assert [section.path for section in sections] == ["Service", "Service > Setup", "Service > Setup > Local"]


def test_structural_chunker_preserves_table_list_and_code_fence() -> None:
    source = """# Setup
Explain the command.

1. Install dependencies.

```sh
make run
```

| Flag | Meaning |
| --- | --- |
| -v | Verbose |
"""
    chunks = chunk_markdown_document(source, title="Setup", document_category=DocumentCategory.SETUP)
    content = "\n".join(chunk.content for chunk in chunks)
    assert "1. Install dependencies." in content
    assert "```sh\nmake run\n```" in content
    assert "| Flag | Meaning |" in content


def test_category_profiles_apply_distinct_cohesion_rules() -> None:
    blocks = [StructuralBlock("paragraph", "Explanation."), StructuralBlock("code", "```sh\nmake run\n```")]
    setup = _bond_blocks(blocks, _PROFILES[DocumentCategory.SETUP])
    overview = _bond_blocks(blocks, _PROFILES[DocumentCategory.OVERVIEW])
    assert len(setup) == 1 and setup[0].kind == "paragraph+code"
    assert len(overview) == 2
    assert _PROFILES[DocumentCategory.ARCHITECTURE].refinement_strength == 2


@pytest.mark.parametrize(
    ("category", "expected_atomic"),
    [
        (DocumentCategory.OVERVIEW, frozenset()),
        (DocumentCategory.ARCHITECTURE, frozenset()),
        (DocumentCategory.SETUP, frozenset({"list", "code"})),
        (DocumentCategory.ACCESS_SECURITY, frozenset({"list", "table", "code"})),
        (DocumentCategory.CODEBASE_GUIDE, frozenset({"code"})),
        (DocumentCategory.CONVENTION, frozenset({"list", "table", "code"})),
        (DocumentCategory.FIRST_TASK, frozenset({"list", "code"})),
    ],
)
def test_every_category_has_its_declared_profile(category: DocumentCategory, expected_atomic: frozenset[str]) -> None:
    assert _PROFILES[category].bonded_atomic_kinds == expected_atomic


def test_selective_refinement_splits_oversized_heterogeneous_section() -> None:
    sentences = " ".join(f"Sentence {index}." for index in range(900))
    source = f"# Architecture\n{sentences}\n\n```text\nimmutable block\n```"
    chunks = chunk_markdown_document(source, title="Architecture", document_category=DocumentCategory.ARCHITECTURE)
    assert len(chunks) > 1
    assert any("immutable block" in chunk.content for chunk in chunks)


def test_secret_scan_redacts_detected_value_without_retaining_value() -> None:
    result = secret_scan_and_redact("safe line\naccess_key = AKIAIOSFODNN7EXAMPLE\n")
    assert result.findings
    assert "AKIA" not in result.redacted_content
    assert "access_key = [REDACTED]" in result.redacted_content
