# Chat module

Owns the grounded end-user question-and-answer use case (F5), its HTTP contract, and its application workflow.

Implement chat request validation, ACL-aware calls to the one `RetrievalEngine`, orchestration calls, and user-safe fallbacks. Do not implement retrieval or provider code locally.
