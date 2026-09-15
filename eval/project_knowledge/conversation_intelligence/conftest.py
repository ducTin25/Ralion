"""Reuse the same in-memory-SQLite `db_session` fixture `tests/` uses, so this fixture's cases
run with a real `ChatService`/`ConversationRepository` against a real (if ephemeral) schema --
only the LLM/retrieval collaborators are faked (see `test_stateful_fixture.py`)."""

from __future__ import annotations

from tests.conftest import allow_header_user_context, db_session  # noqa: F401
