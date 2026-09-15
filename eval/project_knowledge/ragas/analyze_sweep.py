"""Offline confusion-matrix analysis over sweep_report.json — no live calls.

Replays RelevanceGate.accept()'s exact accept condition (dense_ok OR lexical_ok) for a grid of
`min_dense_cosine` values, holding `min_lexical_score` fixed at the current config
(min_lexical_score=0.10), against the real candidate scores captured by sweep_relevance_gate.py.

AUDIT.md F-15 (fixed 2026-08-22): the gate no longer requires `bm25_rank == 1`, and
`sweep_relevance_gate.py` now records a real backfilled `dense_score` for BM25-only candidates
(not a None/0.0 coercion) -- this replay mirrors both changes so the confusion matrix reflects
what the live gate actually does today, not the pre-fix behaviour.
"""
import json
from pathlib import Path

report = json.loads((Path(__file__).parent / "sweep_report.json").read_text(encoding="utf-8"))
records = report["records"]

MIN_LEXICAL_SCORE = 0.10


def would_accept(record, min_dense_cosine: float) -> bool:
    for c in record["candidates"]:
        dense_ok = (c["dense_score"] or 0.0) >= min_dense_cosine
        lexical_ok = c["lexical_overlap"] and (c["bm25_score"] or 0.0) >= MIN_LEXICAL_SCORE
        if dense_ok or lexical_ok:
            return True
    return False


thresholds = [round(0.30 + 0.01 * i, 2) for i in range(0, 51)]  # 0.30 .. 0.80
print(f"{'threshold':>9} | {'answerable_accept':>18} | {'unanswerable_accept(FP)':>24} | {'youden_J':>8}")
for t in thresholds:
    answerable = [r for r in records if r["case_type"] == "answerable"]
    unanswerable = [r for r in records if r["case_type"] == "unanswerable"]
    a_accept = sum(would_accept(r, t) for r in answerable)
    u_accept = sum(would_accept(r, t) for r in unanswerable)
    tpr = a_accept / len(answerable)
    fpr = u_accept / len(unanswerable)
    j = tpr - fpr
    print(f"{t:>9} | {a_accept}/{len(answerable):>15} | {u_accept}/{len(unanswerable):>21} | {j:>8.3f}")

print("\nPer-case max dense_score and lexical bypass eligibility:")
for r in records:
    max_dense = max((c["dense_score"] or 0.0) for c in r["candidates"]) if r["candidates"] else None
    any_lexical = any(
        c["lexical_overlap"] and (c["bm25_score"] or 0.0) >= MIN_LEXICAL_SCORE
        for c in r["candidates"]
    )
    print(f"  {r['case_id']} ({r['case_type']}): max_dense={max_dense:.4f} lexical_bypass_eligible={any_lexical}")
