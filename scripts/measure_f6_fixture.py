"""F6 eval fixture — two-tier measurement runner (CLAUDE.md Phase 4, F6_RULE_MINING_SPEC.md §4.2/4.4).

This is NOT the RuleMiningWorker. It is a standalone, throwaway measurement script for
Phase 4 only: it calls an LLM once per fixture case to produce the same
{evidence_type, reuse_scope, rule_text_draft, rationale} shape that
F6_RULE_MINING_SPEC.md §4.2 step 3 (LLM extraction) will produce in the real pipeline,
then embeds rule_text_draft against the production BGE_M3_ENDPOINT (Modal-hosted, same
model src/infrastructure/ai/modal_embedding_adapter.py calls at request time) and
reports real cosine similarities for the 4 known rule families, per the Phase 4 exit
criteria. (Loading BgeM3Embedder in-process was tried first and abandoned: this
workstation does not have enough free RAM for the local ~2GB model load — see
embed_via_modal()'s docstring below.)

Model substitution note (measured, not assumed): the production chat model configured
in .env (OPENROUTER_MODEL=openai/gpt-4o-mini via OPENROUTER_API_KEY) returned HTTP 401
in this environment at the time this script was written — that credential is not live.
DEEPSEEK_API_KEY in .env *is* live (verified with a direct call before running this
script). Tier 1 numbers below were measured against deepseek-chat, not gpt-4o-mini.
This is disclosed, not hidden: re-run with --model/--base-url/--api-key-env pointed at
the real production model once that credential is live, before trusting Tier 1 numbers
for a go/no-go call on prompt quality. Tier 2 (embedding/clustering) is unaffected by
which LLM produced rule_text_draft — bge-m3 is the same model the production pipeline
will use either way.

Usage:
    .venv/Scripts/python.exe scripts/measure_f6_fixture.py
    .venv/Scripts/python.exe scripts/measure_f6_fixture.py --skip-llm   # tier 2 only, reuse cached tier-1 output
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from itertools import combinations
from pathlib import Path

from dotenv import load_dotenv

REPO_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_PATH = REPO_ROOT / "golden-test" / "f6_eval_fixture.json"
REPORT_PATH = REPO_ROOT / "golden-test" / "f6_eval_fixture_measurement_report.json"

EVIDENCE_TYPES = [
    "REUSABLE_CORRECTION",
    "CONVENTION",
    "LOCAL_CORRECTION",
    "RATIONALE",
    "QUESTION_DISCUSSION",
    "NOISE_OTHER",
]

SYSTEM_PROMPT = """You classify one PR review evidence unit from thanos-io/thanos for F6 Rule Mining.

Output STRICT JSON with exactly these 4 keys, no others:
{
  "evidence_type": one of REUSABLE_CORRECTION | CONVENTION | LOCAL_CORRECTION | RATIONALE | QUESTION_DISCUSSION | NOISE_OTHER,
  "reuse_scope": integer 0, 1, or 2,
  "rule_text_draft": string,
  "rationale": string
}

evidence_type definitions:
- REUSABLE_CORRECTION: reviewer points out a mistake/anti-pattern and the correction generalizes to
  other code beyond the spot being fixed (test: "would this comment apply again 6 months from now on
  unrelated code written the old way?").
- CONVENTION: reviewer states an existing project convention/pattern (style, naming, structure, error
  handling...) the PR violates or should follow, not tied to one specific bug.
- LOCAL_CORRECTION: correction only valid at this specific spot, tied to this function's business logic,
  does not generalize.
- RATIONALE: explains WHY a design decision was made; not a correction, not a convention.
- QUESTION_DISCUSSION: pure question or inconclusive discussion.
- NOISE_OTHER: none of the above (administrative, CI status, thanks/LGTM, filter artifact).

reuse_scope definitions (only meaningful when evidence_type is REUSABLE_CORRECTION or CONVENTION):
- 0: only true for the exact case being fixed.
- 1: applies to a specific subsystem/API/pattern, not the whole codebase.
- 2: applies project-wide (style guide, error handling pattern, naming convention, etc. that applies
  everywhere). Most real conventions are 1, not 2 — do not default to 2 just because something "sounds
  important".

rule_text_draft: ONE normalized sentence stating the rule, independent of this specific function's
business logic (so two syntactically different comments that express the same underlying rule produce
similar sentences). Empty string if evidence_type is not REUSABLE_CORRECTION or CONVENTION.

rationale: the explicit reason stated in the evidence text (look for "because", "since", "to avoid", "so
that", etc.), copied/paraphrased from the text. If no explicit reason is stated in the text, output
exactly: "No explicit rationale found in the evidence." Do not invent a reason.

Respond with the JSON object only, no markdown fences, no commentary."""


@dataclass
class Tier1Result:
    evidence_unit_id: str
    expected_evidence_type: str
    expected_reuse_scope: int
    predicted_evidence_type: str | None
    predicted_reuse_scope: int | None
    rule_text_draft: str
    rationale: str
    evidence_type_match: bool
    reuse_scope_match: bool
    error: str | None = None


def run_tier1(cases: list[dict], model: str, base_url: str, api_key: str) -> list[Tier1Result]:
    import openai

    client = openai.OpenAI(api_key=api_key, base_url=base_url)
    results: list[Tier1Result] = []
    for case in cases:
        user_content = "Evidence unit comments (in order):\n\n" + "\n\n---\n\n".join(case["raw_comment_bodies"])
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0,
                max_tokens=400,
                response_format={"type": "json_object"},
            )
            parsed = json.loads(resp.choices[0].message.content)
            predicted_type = parsed.get("evidence_type")
            predicted_scope = parsed.get("reuse_scope")
            predicted_scope = int(predicted_scope) if predicted_scope is not None else None
            results.append(
                Tier1Result(
                    evidence_unit_id=case["evidence_unit_id"],
                    expected_evidence_type=case["expected_evidence_type"],
                    expected_reuse_scope=case["expected_reuse_scope"],
                    predicted_evidence_type=predicted_type,
                    predicted_reuse_scope=predicted_scope,
                    rule_text_draft=parsed.get("rule_text_draft", ""),
                    rationale=parsed.get("rationale", ""),
                    evidence_type_match=predicted_type == case["expected_evidence_type"],
                    reuse_scope_match=(
                        predicted_scope is not None
                        and abs(predicted_scope - case["expected_reuse_scope"]) <= 1
                    ),
                )
            )
        except Exception as exc:  # noqa: BLE001 - measurement script, surface any failure per-case
            results.append(
                Tier1Result(
                    evidence_unit_id=case["evidence_unit_id"],
                    expected_evidence_type=case["expected_evidence_type"],
                    expected_reuse_scope=case["expected_reuse_scope"],
                    predicted_evidence_type=None,
                    predicted_reuse_scope=None,
                    rule_text_draft="",
                    rationale="",
                    evidence_type_match=False,
                    reuse_scope_match=False,
                    error=str(exc),
                )
            )
        print(f"  tier1: {case['evidence_unit_id']} done")
    return results


# Human-authored, one-sentence normalized rule statements for all 25 fixture cases — a
# CONTROL for tier 2, isolating the embedding/clustering threshold question from tier 1's
# extraction-accuracy question. NOT LLM output. Written by applying the exact same test
# annotation_guide.md §3.9 gives a human for recognizing family membership ("if I wrote this
# rule as one sentence, do both evidence units satisfy the same sentence?") to each case's
# raw_comment_bodies. Needed because tier 1 (deepseek-chat, zero-shot) only produced a real
# rule_text_draft for 15/25 cases (see tier1 results) — too few of the 8 known-family members
# to compute a clean 4-pair table from LLM output alone in this run.
HAND_AUTHORED_RULE_TEXT_DRAFT = {
    "THANOS_8378_E3": "Remove comments that only restate what is already obvious from the code.",
    "THANOS_8594_E1": "When wrapping a third-party config struct, expose only the fields actually "
    "needed and document them with a link to the upstream docs.",
    "THANOS_8594_E13": "Prefer using modern language constructs over hand-rolled boilerplate for "
    "constructing pointer-typed config fields.",
    "THANOS_8594_E19": "Centralize a scattered set of allowed values into a single source of truth "
    "instead of duplicating the list across multiple places.",
    "THANOS_8594_E2": "Name validation functions after exactly what they validate, and keep such "
    "helpers private unless they need to be exported.",
    "THANOS_8594_E21": "Avoid shallow functions that are called from just one place; inline them "
    "or expose the underlying function directly instead.",
    "THANOS_8594_E4": "Link configuration fields to their upstream library documentation in code "
    "comments.",
    "THANOS_8594_E8": "Run the docs/whitespace lint target before submitting so CI docs checks pass.",
    "THANOS_8630_E2": "Prefer idiomatic modern range-over-int loops over manual index loops.",
    "THANOS_8630_E3": "Remove small comments that just restate obvious code behavior; they are "
    "distracting.",
    "THANOS_8648_E1": "A mutex should be owned by, and protect, the specific struct/state it guards, "
    "not a sibling container; expose access via a method on that struct.",
    "THANOS_8691_E2": "Collect a set of related paths into a slice and loop over it instead of "
    "repeating near-identical calls.",
    "THANOS_8691_E3": "Skip making a remote API call when the operation is a no-op for that provider.",
    "THANOS_8713_E1": "When a per-worker metric label is created, make sure it is also deleted when "
    "that worker is removed, to avoid unbounded cardinality.",
    "THANOS_8720_E2": "Use errors.Is, not direct comparison, to match sentinel or wrapped errors.",
    "THANOS_8720_E3": "Don't move request-path work onto a background goroutine without admission "
    "control; keep it synchronous inline to avoid backpressure regressions.",
    "THANOS_8801_E1": "Extract a magic literal into a named constant and add a comment explaining "
    "why that value was chosen.",
    "THANOS_8806_E1": "Prefer a focused handler-level test over an e2e test when you need to assert "
    "on the exact error/response code.",
    "THANOS_8806_E2": "Prefer a focused handler-level test over an e2e test when you need to assert "
    "on the exact error/response code.",
    "THANOS_8808_E2": "Don't change an existing protobuf field's type in place; reserve its field "
    "number and add a new field instead, to keep wire compatibility with older readers.",
    "THANOS_8840_E2": "Remove LLM-generated writing tics (narrated history, verbose backstory) from "
    "PR content; keep comments focused on the current code, not the change's history.",
    "THANOS_8894_E1": "When a protobuf field becomes unused, reserve its field number instead of "
    "repurposing or deleting it outright.",
    "THANOS_8907_E1": "Don't encode a specific version/environment detail into a required CI check's "
    "name; keep required-check names generic so renames don't silently break branch protection.",
    "THANOS_8935_E1": "Avoid creating functions that are only called from one place; keep the "
    "interface narrow instead of adding shallow wrapper functions.",
    "THANOS_8944_E1": "Remove LLM-generated writing tics (dramatic/narrated prose) from comments and "
    "changelog entries when the change isn't user-visible.",
}


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = sum(x * x for x in a) ** 0.5
    norm_b = sum(y * y for y in b) ** 0.5
    return dot / (norm_a * norm_b)


def embed_via_modal(texts: list[str]) -> tuple[list[list[float]], str, int]:
    """Call the production BGE-M3 endpoint (src/infrastructure/ai/modal_embedding_adapter.py's
    target) directly over HTTP. Used instead of loading BgeM3Embedder in-process because this
    workstation does not have enough free RAM to load the ~2GB local model (measured: local
    load crashed with a Rust allocator OOM at ~67MB alloc against ~700MB free physical memory).
    Same model/weights either way — this hits the same Modal deployment production's
    ModalEmbeddingAdapter calls, just without the async retry/budget machinery that only
    matters for a live request path.
    """
    import httpx

    endpoint = os.environ["BGE_M3_ENDPOINT"]
    api_key = os.environ["BGE_M3_API_KEY"]
    resp = httpx.post(
        f"{endpoint.rstrip('/')}/embed",
        json={"texts": texts},
        headers={"Authorization": f"Bearer {api_key}"},
        timeout=120,
    )
    resp.raise_for_status()
    data = resp.json()
    return data["vectors"], data["model"], data["dimension"]


def run_tier2(cases: list[dict], text_by_id: dict[str, str], fallback_ids: list[str]) -> dict:
    """Embed text_by_id[uid] for every case and report known-family / cross-family cosine.

    text_by_id must have an entry for every case's evidence_unit_id. fallback_ids marks which
    of those entries are NOT genuine rule_text_draft (see callers in main()) so pairs touching
    them can be flagged instead of silently blended into the same numbers as clean pairs.
    """
    ids = [c["evidence_unit_id"] for c in cases]
    texts = [text_by_id[uid] for uid in ids]

    print(f"  embedding {len(texts)} strings via BGE_M3_ENDPOINT...")
    vectors, model_version, dimension = embed_via_modal(texts)
    vec_by_id = dict(zip(ids, vectors, strict=True))

    fam_by_id = {c["evidence_unit_id"]: c["expected_rule_family_id"] for c in cases}
    conf_by_id = {c["evidence_unit_id"]: c["expected_family_match_confidence"] for c in cases}

    known_family_pairs = []
    families: dict[str, list[str]] = {}
    for uid, fam in fam_by_id.items():
        if fam:
            families.setdefault(fam, []).append(uid)
    for fam, members in families.items():
        for a, b in combinations(members, 2):
            known_family_pairs.append(
                {
                    "family": fam,
                    "expected_confidence": conf_by_id[a],
                    "pair": [a, b],
                    "cosine": cosine(vec_by_id[a], vec_by_id[b]),
                }
            )

    # Cross-family pairs: one representative evidence unit per known family, all C(4,2)=6
    # combinations, plus 2 CONVENTION-vs-CONVENTION singleton pairs picked as
    # highest-confusion-risk (same evidence_type, different topic).
    reps = {fam: members[0] for fam, members in families.items()}
    cross_family_pairs = []
    for (fam_a, uid_a), (fam_b, uid_b) in combinations(reps.items(), 2):
        cross_family_pairs.append(
            {
                "pair_kind": "cross_known_family",
                "families": [fam_a, fam_b],
                "pair": [uid_a, uid_b],
                "cosine": cosine(vec_by_id[uid_a], vec_by_id[uid_b]),
            }
        )

    convention_singletons = [
        c["evidence_unit_id"]
        for c in cases
        if c["expected_evidence_type"] == "CONVENTION" and not c["expected_rule_family_id"]
    ]
    for a, b in combinations(convention_singletons, 2):
        cross_family_pairs.append(
            {
                "pair_kind": "convention_singleton_vs_singleton",
                "families": [None, None],
                "pair": [a, b],
                "cosine": cosine(vec_by_id[a], vec_by_id[b]),
            }
        )

    full_matrix = {a: {b: cosine(vec_by_id[a], vec_by_id[b]) for b in ids} for a in ids}

    for pair_list in (known_family_pairs, cross_family_pairs):
        for p in pair_list:
            p["used_fallback_text"] = [uid in fallback_ids for uid in p["pair"]]

    return {
        "embedding_model": model_version,
        "embedding_dimension": dimension,
        "fallback_text_case_ids": fallback_ids,
        "known_family_pairs": known_family_pairs,
        "cross_family_pairs": cross_family_pairs,
        "full_pairwise_cosine_matrix": full_matrix,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", default="deepseek-chat")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument("--api-key-env", default="DEEPSEEK_API_KEY")
    parser.add_argument("--skip-llm", action="store_true", help="Reuse tier1 output already in the report file")
    args = parser.parse_args()

    load_dotenv(REPO_ROOT / ".env")

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    cases = fixture["cases"]

    if args.skip_llm:
        existing = json.loads(REPORT_PATH.read_text(encoding="utf-8"))
        tier1_results = [Tier1Result(**r) for r in existing["tier1"]["results"]]
    else:
        api_key = os.environ.get(args.api_key_env, "")
        if not api_key:
            raise SystemExit(f"{args.api_key_env} not set in environment/.env")
        print(f"Running tier 1 (LLM extraction) against model={args.model} base_url={args.base_url} ...")
        tier1_results = run_tier1(cases, args.model, args.base_url, api_key)

    tier1_by_id = {r.evidence_unit_id: r for r in tier1_results}
    n_type_match = sum(1 for r in tier1_results if r.evidence_type_match)
    n_scope_match = sum(1 for r in tier1_results if r.reuse_scope_match)
    n_errors = sum(1 for r in tier1_results if r.error)

    # Persist tier1 immediately so a tier2 failure doesn't lose paid LLM calls.
    REPORT_PATH.write_text(
        json.dumps({"tier1": {"results": [asdict(r) for r in tier1_results]}}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    llm_text_by_id = {}
    fallback_ids = []
    for c in cases:
        uid = c["evidence_unit_id"]
        t1 = tier1_by_id.get(uid)
        text = t1.rule_text_draft if t1 and t1.rule_text_draft else None
        if not text:
            # Tier1 LLM misclassified this case (didn't return REUSABLE_CORRECTION/CONVENTION,
            # so no rule_text_draft was produced) — fall back to the raw comment body so this
            # variant still gets a complete cosine table. A pair touching a fallback id is NOT
            # measuring the production pipeline's actual behavior (§4.3 only ever embeds
            # rule_text_draft) — it's "what if raw text were embedded instead" for that node.
            text = " ".join(c["raw_comment_bodies"])
            fallback_ids.append(uid)
        llm_text_by_id[uid] = text

    print("Running tier 2a (as-observed: tier1 rule_text_draft, raw-body fallback where LLM missed) ...")
    tier2_as_observed = run_tier2(cases, llm_text_by_id, fallback_ids)

    clean_text_by_id = {c["evidence_unit_id"]: HAND_AUTHORED_RULE_TEXT_DRAFT[c["evidence_unit_id"]] for c in cases}
    print("Running tier 2b (control: hand-authored normalized rule text, all 25 cases) ...")
    tier2_clean_control = run_tier2(cases, clean_text_by_id, fallback_ids=[])

    report = {
        "meta": {
            "fixture": "golden-test/f6_eval_fixture.json",
            "n_cases": len(cases),
            "tier1_model": args.model,
            "tier1_model_note": (
                "Production chat model (OPENROUTER_MODEL) had no live credential in this "
                "environment; deepseek-chat used as a measured stand-in. Re-run against the "
                "real production model before treating tier1 numbers as final."
                if args.model == "deepseek-chat"
                else "measured against configured model"
            ),
            "tier2_variants": {
                "as_observed": "embeds tier1's actual rule_text_draft output; raw comment body "
                "fallback for the 10 cases tier1 misclassified (see fallback_text_case_ids)",
                "clean_control": "embeds 25 hand-authored (not LLM) one-sentence normalized rule "
                "statements — isolates the embedding/clustering threshold question from tier1 "
                "extraction accuracy",
            },
        },
        "tier1": {
            "evidence_type_match_rate": n_type_match / len(cases),
            "reuse_scope_match_rate_within_1_tier": n_scope_match / len(cases),
            "n_errors": n_errors,
            "results": [asdict(r) for r in tier1_results],
        },
        "tier2_as_observed": tier2_as_observed,
        "tier2_clean_control": tier2_clean_control,
    }
    REPORT_PATH.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    print("\n=== TIER 1 (LLM extraction, measured against", args.model, ") ===")
    print(f"evidence_type exact match: {n_type_match}/{len(cases)} ({n_type_match/len(cases):.1%})")
    print(f"reuse_scope within 1 tier: {n_scope_match}/{len(cases)} ({n_scope_match/len(cases):.1%})")
    if n_errors:
        print(f"errors: {n_errors}")

    for label, tier2 in (("2a AS-OBSERVED", tier2_as_observed), ("2b CLEAN CONTROL", tier2_clean_control)):
        print(f"\n=== TIER {label} (bge-m3 cosine, known-family pairs) ===")
        for p in tier2["known_family_pairs"]:
            fb = " [FALLBACK]" if any(p["used_fallback_text"]) else ""
            print(f"  {p['family']:40s} exp={p['expected_confidence']:6s} cosine={p['cosine']:.4f}  {p['pair']}{fb}")

        print(f"=== TIER {label} (bge-m3 cosine, cross-family / confusion-risk pairs) ===")
        for p in tier2["cross_family_pairs"]:
            fb = " [FALLBACK]" if any(p["used_fallback_text"]) else ""
            print(f"  {p['pair_kind']:35s} cosine={p['cosine']:.4f}  {p['pair']}  families={p['families']}{fb}")

    print(f"\nFull report written to {REPORT_PATH}")


if __name__ == "__main__":
    main()
