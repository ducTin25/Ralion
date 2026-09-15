# Chat application workflow

Contains the LangGraph workflow used by the chat use case.

Implement the sequence retrieve context → generate answer → validate citations → return fallback if invalid. Keep nodes small and put provider details in `src/ai`.
