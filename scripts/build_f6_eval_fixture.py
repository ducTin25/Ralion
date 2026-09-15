"""Build golden-test/f6_eval_fixture.json from the already-annotated
thanos_comments_annotated_DRAFT.csv (F6_RULE_MINING_SPEC.md CLAUDE.md Phase 4).

Read-only against the CSV: no re-annotation happens here. This just projects the
138 annotated rows down to the 25 evidence units eligible for build_rule_families
(evidence_type IN {REUSABLE_CORRECTION, CONVENTION} AND reuse_scope >= 1, per
F6_RULE_MINING_SPEC.md mục 2.1/5.3), grouping raw comment rows by evidence_unit_id
in CSV order.

Usage:
    python scripts/build_f6_eval_fixture.py
"""

from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSV = REPO_ROOT / "scripts" / "thanos_comments_annotated_DRAFT.csv"
OUTPUT_JSON = REPO_ROOT / "golden-test" / "f6_eval_fixture.json"

ELIGIBLE_TYPES = {"REUSABLE_CORRECTION", "CONVENTION"}

KNOWN_FAMILIES = {
    "THANOS_FAM_avoid_shallow_functions": "HIGH",
    "THANOS_FAM_avoid_llmisms": "HIGH",
    "THANOS_FAM_avoid_redundant_comments": "HIGH",
    "THANOS_FAM_protobuf_field_compat": "MEDIUM",
}


def main() -> None:
    with SOURCE_CSV.open(encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))

    units: dict[str, list[dict]] = {}
    for row in rows:
        uid = row["evidence_unit_id"].strip()
        if uid:
            units.setdefault(uid, []).append(row)

    cases = []
    for uid, members in units.items():
        evidence_type = members[0]["evidence_type"]
        reuse_scope_raw = members[0]["reuse_scope"]
        if evidence_type not in ELIGIBLE_TYPES or reuse_scope_raw in ("", "0"):
            continue

        types = {m["evidence_type"] for m in members}
        scopes = {m["reuse_scope"] for m in members}
        if len(types) != 1 or len(scopes) != 1:
            raise ValueError(f"Inconsistent labels within evidence unit {uid}: types={types} scopes={scopes}")

        family_id = members[0]["rule_family_id"].strip() or None
        confidence = members[0]["family_match_confidence"].strip() or None
        if family_id is not None and family_id not in KNOWN_FAMILIES:
            raise ValueError(f"Unexpected rule_family_id {family_id!r} for {uid} — not one of the 4 known families")
        if family_id is not None and confidence != KNOWN_FAMILIES[family_id]:
            raise ValueError(
                f"{uid}: family_match_confidence in CSV ({confidence!r}) does not match "
                f"SPEC-fixed value for {family_id} ({KNOWN_FAMILIES[family_id]!r})"
            )

        cases.append(
            {
                "evidence_unit_id": uid,
                "pr_number": int(members[0]["pr_number"]),
                "raw_comment_bodies": [m["body"] for m in members],
                "expected_evidence_type": evidence_type,
                "expected_reuse_scope": int(reuse_scope_raw),
                "expected_rule_family_id": family_id,
                "expected_family_match_confidence": confidence,
                "expected_f7_operationalizability": int(members[0]["f7_operationalizability"]),
            }
        )

    cases.sort(key=lambda c: (c["pr_number"], c["evidence_unit_id"]))

    n_reusable = sum(1 for c in cases if c["expected_evidence_type"] == "REUSABLE_CORRECTION")
    n_convention = sum(1 for c in cases if c["expected_evidence_type"] == "CONVENTION")
    n_family = sum(1 for c in cases if c["expected_rule_family_id"])
    if len(cases) != 25 or n_reusable != 19 or n_convention != 6 or n_family != 8:
        raise ValueError(
            f"Fixture extraction produced unexpected counts: total={len(cases)} "
            f"reusable={n_reusable} convention={n_convention} in_family={n_family} "
            f"(expected 25/19/6/8 per F6_RULE_MINING_SPEC.md mục 2.1 review)"
        )

    fixture = {
        "meta": {
            "version": "1.0",
            "source_csv": "scripts/thanos_comments_annotated_DRAFT.csv",
            "source_report": "scripts/thanos_annotation_DRAFT_report.md",
            "repo": "thanos-io/thanos",
            "window": "2025-08-01..2026-07-31",
            "sample_pr_count": 120,
            "eligibility_contract": "evidence_type IN (REUSABLE_CORRECTION, CONVENTION) AND reuse_scope >= 1 "
            "(F6_RULE_MINING_SPEC.md mục 2.1)",
            "total_cases": len(cases),
            "evidence_type_distribution": {"REUSABLE_CORRECTION": n_reusable, "CONVENTION": n_convention},
            "known_rule_families": KNOWN_FAMILIES,
            "singleton_case_count": len(cases) - n_family,
            "notes": [
                "17/25 cases are singletons (expected_rule_family_id=null) — no second evidence found in "
                "this 120-PR sample, per F6_RULE_MINING_SPEC.md mục 3.1 (a sample-power question, not a "
                "repo-quality verdict).",
                "raw_comment_bodies is untruncated per row, in original CSV order — density_check.py's "
                "500-char truncation bug (fixed in F6_RULE_MINING_SPEC.md mục 1.1) did not affect any label "
                "in this dataset (mục 1.3).",
            ],
        },
        "cases": cases,
    }

    OUTPUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON.write_text(json.dumps(fixture, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(cases)} cases to {OUTPUT_JSON}")


if __name__ == "__main__":
    main()
