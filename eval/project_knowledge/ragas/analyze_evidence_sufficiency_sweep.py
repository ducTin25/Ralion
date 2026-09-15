"""Offline confusion-matrix analysis over sweep_evidence_sufficiency_gate_report.json.

No live calls -- turns the recorded per-case verdicts from
`sweep_evidence_sufficiency_gate.py` into a 2x2 confusion matrix against `case_type`
(answerable vs unanswerable), the same shape `analyze_sweep.py` produces for the
RelevanceGate threshold. This is the number CHANGE_LOG.md records before
`chat.evidence_sufficiency_gate.enabled` is flipped to true in `config/chunking_params.yaml`.

Definitions, combining the RelevanceGate accept decision with this gate's verdict, since that
composition is exactly what a real turn in `_ask_traced` goes through:
  - "would answer" (predicted positive) = RelevanceGate accepted something AND
    (this gate not called i.e. accepted was empty is impossible here, since gate_called implies
    accepted non-empty) AND the gate's verdict.sufficient is True.
  - RelevanceGate-rejected cases (accepted empty) already fall back as no_evidence upstream of
    this gate -- they count as "would answer" = False without ever reaching it.
  - A gate error (`errored: true`) fails CLOSED -- counts as "would answer" = False
    (fallback_reason=system_error, still not a hallucinated answer).
"""
import json
from pathlib import Path

report = json.loads(
    (Path(__file__).parent / "sweep_evidence_sufficiency_gate_report.json").read_text(encoding="utf-8")
)
records = report["records"]


def would_answer(record: dict) -> bool:
    if not record["accepted_chunk_ids"]:
        return False  # RelevanceGate already rejected -> no_evidence, gate never reached
    if record["verdict"] is None:
        return False  # retrieval or gate error -> system_error fallback
    if record["verdict"]["errored"]:
        return False  # fail-closed -> system_error fallback
    return bool(record["verdict"]["sufficient"])


answerable = [r for r in records if r["case_type"] == "answerable"]
unanswerable = [r for r in records if r["case_type"] == "unanswerable"]

a_answer = sum(would_answer(r) for r in answerable)
u_answer = sum(would_answer(r) for r in unanswerable)

print(f"answerable:   {a_answer}/{len(answerable)} would answer (recall -- higher is better)")
print(f"unanswerable: {u_answer}/{len(unanswerable)} would answer (false positives -- 0 is the target)")
print()
print("Per-case detail:")
for r in records:
    reason = (
        "relevance_gate_rejected" if not r["accepted_chunk_ids"]
        else "retrieval_or_gate_error" if r["verdict"] is None
        else "gate_errored_fail_closed" if r["verdict"]["errored"]
        else "gate_sufficient" if r["verdict"]["sufficient"]
        else "gate_insufficient"
    )
    print(
        f"  {r['case_id']} ({r['case_type']}): accepted={r['accepted_chunk_ids']} "
        f"-> {reason} -> would_answer={would_answer(r)}"
    )
