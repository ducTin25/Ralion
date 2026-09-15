# AnswerGenerator capability A/B

## Decision

`gpt-5.6-luna` with `reasoning_effort=none` materially improves the frozen-evidence
completeness cluster, but is slower and more verbose. Use it only for AnswerGenerator if the
interactive latency budget can absorb its +0.94 s generation p50 and +2.22 s p95; retain the
current cheaper/faster model for routing and other short classification calls.

## Controlled design

- Source artifact: `full_eval_20260830T151752Z.json`.
- Artifact candidate rule: `INCOMPLETE_ANSWER`, recall@5=1, a primary aspect >=0.5, and another
  required aspect <1. This yielded 19 candidates.
- Common live capture applied the production RelevanceGate once and reused the same accepted
  evidence objects for both arms. Two candidates had no accepted evidence and were excluded:
  `F5V2-PRJ-023`, `F5V2-PRJ-029`.
- Final tested cluster (17): `F5V2-POL-010`, `F5V2-POL-015`, `F5V2-POL-017`, `F5V2-POL-022`,
  `F5V2-POL-024`, `F5V2-POL-031`, `F5V2-POL-042`, `F5V2-PRJ-001`, `F5V2-PRJ-002`,
  `F5V2-PRJ-005`, `F5V2-PRJ-007`, `F5V2-PRJ-010`, `F5V2-PRJ-011`, `F5V2-PRJ-012`,
  `F5V2-PRJ-013`, `F5V2-PRJ-036`, `F5V2-PRJ-037`.
- Three paired, interleaved repetitions per case (51 runs/arm). Prompt `grounded-answer-v10`,
  answer token ceiling 4096, temperature 0, validation/repair and citations were unchanged.
- A: exact production AnswerGenerator (`gpt-4o-mini-2024-07-18`). B: `gpt-5.6-luna`,
  `reasoning_effort=none`.

## Aggregate

| Metric                                  | A: GPT-4o mini |  B: Luna none |    Difference |
| --------------------------------------- | -------------: | ------------: | ------------: |
| Mean task completeness                  |          0.556 |         0.753 |        +0.197 |
| Material-omission runs                  |  44/50 (88.0%) | 25/51 (49.0%) |      -39.0 pp |
| Mean claim faithfulness                 |          0.920 |         0.989 |        +0.069 |
| Anchor failures                         |              0 |             0 |             0 |
| Fallback rate                           |           2.0% |          0.0% |       -2.0 pp |
| Validator/repair degradation or failure |           3/51 |         11/51 |         +8/51 |
| Mean output tokens                      |          116.6 |         265.8 | +149.2 (128%) |
| Mean answer characters                  |          154.6 |         327.5 | +172.9 (112%) |
| Generation p50                          |        1.328 s |       2.266 s |      +0.938 s |
| Generation p95                          |        3.250 s |       5.469 s |      +2.219 s |
| Generation p99                          |        5.296 s |      10.484 s |      +5.188 s |

The complete per-run output, frozen-evidence hashes, answers, claim/citation validation data,
and judge notes are in the adjacent JSON artifact.
