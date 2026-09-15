from src.ai.retrieval_engine.policy_chunker import (
    _default_token_count,
    chunk_policy_markdown,
    embedding_text_for_policy_chunk,
)


def test_default_token_count_falls_back_when_tokenizer_data_is_unavailable(monkeypatch):
    import tiktoken

    def unavailable(_name: str):
        raise OSError("tokenizer data unavailable")

    monkeypatch.setattr(tiktoken, "get_encoding", unavailable)

    assert _default_token_count("mot hai ba") == 3


def count_words(text: str) -> int:
    return len(text.split())


def test_policy_chunker_keeps_table_and_numbered_procedure_atomic() -> None:
    markdown = """# Policy

## 1. Purpose
Short purpose.

## 2. Procedure
1. Submit the request.
2. Manager approves the request.
3. HR records the result.

| SLA | Response |
|---|---|
| P1 | 1 hour |

## 3. Notes
This is a final note.
"""
    chunks = chunk_policy_markdown(
        markdown,
        document_code="HR-POL-001",
        config={
            "policy": {
                "target_size_tokens_min": 200,
                "target_size_tokens_max": 400,
                "hard_ceiling_tokens": 700,
                "force_split_overlap_tokens_min": 20,
                "force_split_overlap_tokens_max": 40,
            }
        },
        token_count=count_words,
    )
    atomic = [chunk for chunk in chunks if chunk.is_atomic]
    assert len(atomic) == 2
    assert "1. Submit" in atomic[0].content
    assert "| P1 | 1 hour |" in atomic[1].content
    assert [chunk.heading_path for chunk in chunks] == [
        "1. Purpose", "2. Procedure", "2. Procedure", "3. Notes"
    ]


def test_embedding_text_adds_context_without_changing_display_content() -> None:
    markdown = "## 1. Purpose\nThis policy applies to all employees."
    chunk = chunk_policy_markdown(markdown, document_code="HR-POL-001", token_count=count_words)[0]
    embedding_text = embedding_text_for_policy_chunk(
        chunk, document_code="HR-POL-001", purpose_sentence="Defines the company leave policy."
    )
    assert chunk.content == "This policy applies to all employees."
    assert embedding_text.startswith("HR-POL-001 › 1. Purpose")
    assert chunk.content in embedding_text
