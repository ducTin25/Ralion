# Legacy golden sets — superseded, kept for provenance

The F5 golden suite now lives in `eval/golden-test/f5_v2/` and is validated by
`eval/validate_golden.py` / `eval/test_golden_suite_v2.py`. The files below are the inputs it
was built from. They are **frozen**: no runner reads them, and they must not be extended.

| File | What it was | Status |
| --- | --- | --- |
| `golden_test_f5_70_samples.json` | 70 POLICY cases (40 RAG / 15 guardrail / 15 injection) | superseded by `f5_v2/` |
| `golden_test_50_samples.json` | 50 POLICY cases, never wired to any runner | superseded by `f5_v2/` |
| `f6_eval_fixture*.json`, `f6_mining_pipeline_fixture_report.json` | F6 rule-mining fixtures | unrelated to F5, still live |

## Why they were retired rather than updated

Both files were written against `raw-data/company-policy/`, which no longer exists: the
authoritative corpus is now `demo-data/company-policy/`, whose documents were **enriched** to
roughly twice their previous length. Re-verifying every quote against the enriched corpus gave:

- `golden_test_f5_70_samples.json` — 52 of 53 evidence-bearing cases still verbatim-valid;
- `golden_test_50_samples.json` — 38 of 48 still valid, 10 broken
  (`GT-007/015/019/027/028/029/040/041/042/047`).

Keeping two golden suites in parallel would have meant maintaining the same facts twice, which is
exactly the duplication the eval architecture is supposed to avoid. So the surviving cases were
migrated into `f5_v2/` individually, each recording where it came from in `provenance.origin`
(`reused:F5-RAG-001`, `rewritten:F5-RAG-013`, ...), and the legacy files were frozen.

`eval/test_golden_set_f5.py` was deleted with them: it asserted "exactly 70 cases" and verified
quotes against `raw-data/`, so it could not survive either change.

## One case was obsolete, not merely re-pathed

`F5-RAG-013` expected the answer "45 ngày / 30 ngày / 3 ngày" for resignation notice periods. The
enriched `HR-POL-003` deliberately removed those hard-coded numbers — `demo-data/company-policy/
README.md` records the change: *"HR-POL-003 không hard-code một mốc báo trước thử việc cho mọi
trường hợp"*. Preserving the case would have pinned a fact the corpus no longer states.

It is rewritten as `F5V2-POL-017`, which inverts the test: the three old numbers are now
`forbidden_substrings`, so the case detects a model answering from the stale corpus or from
pretrained knowledge.

The same audit found one obsolete case in the PROJECT set: `pk_017` (in
`eval/project_knowledge/ragas/golden_dataset.jsonl`) asserted that no per-GB storage price exists
in the corpus, but `test_upload/ARCHITECTURE.md` — ingested as part of the demo corpus — states
one. It was removed and replaced by an answerable v2 case rather than left asserting a false
absence.
