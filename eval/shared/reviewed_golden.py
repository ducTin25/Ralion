"""Binding for the human-reviewed 10-column sheet and the executable F5 v2 fixtures.

The CSV deliberately stays compact and does not duplicate chunk-level evidence.  The JSON suite
remains the executable evidence fixture; this module makes the reviewed semantic contract visible
to that suite and rejects silently stale/missing bindings.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
REVIEWED_PATH = REPO_ROOT / "eval" / "golden-test" / "ralion_initial_golden_set_draft.csv"
HEADER = (
    "ID", "Input", "Domain", "Question Type", "Difficulty", "Metrics", "Expected Route",
    "Answerable?", "Ground Truth / Expected Behavior", "Test File",
)


@dataclass(frozen=True)
class ReviewedGoldenRow:
    id: str
    input: str
    domain: str
    expected_route: str
    answerable: str
    ground_truth: str


def load_reviewed_rows(path: Path = REVIEWED_PATH) -> dict[str, ReviewedGoldenRow]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if tuple(reader.fieldnames or ()) != HEADER:
            raise ValueError("reviewed golden CSV does not use the required 10-column header")
        rows = {
            row["ID"]: ReviewedGoldenRow(
                id=row["ID"], input=row["Input"], domain=row["Domain"],
                expected_route=row["Expected Route"], answerable=row["Answerable?"],
                ground_truth=row["Ground Truth / Expected Behavior"],
            )
            for row in reader
        }
    if len(rows) == 0:
        raise ValueError("reviewed golden CSV is empty")
    return rows


def reviewed_id_for(case_id: str) -> str | None:
    """Map executable `F5V2-*` ids to their reviewed-sheet counterparts."""
    # The reviewed conversational scenarios replaced older short fixtures: the project scenario
    # intentionally reuses the existing PROJECT conversation slot (CNV-008), and the reviewed
    # temporary-access coreference row binds to its equivalent existing fixture (CNV-010).
    # CNV-009 stays JSON-native for backward-compatible coverage of a separate preference check.
    if case_id == "F5V2-CNV-008":
        return "RGS-CNV-009"
    if case_id == "F5V2-CNV-010":
        return "RGS-CNV-008"
    if case_id == "F5V2-CNV-009":
        return None
    prefix_map = {
        "F5V2-POL-": "RGS-POL-", "F5V2-PRJ-": "RGS-PRJ-", "F5V2-CNV-": "RGS-CNV-",
        "F5V2-ADV-": "RGS-ADV-", "F5V2-GRD-": "RGS-GRD-",
    }
    for source, reviewed in prefix_map.items():
        if case_id.startswith(source):
            return reviewed + case_id.removeprefix(source)
    return None


def row_for(case_id: str, rows: dict[str, ReviewedGoldenRow]) -> ReviewedGoldenRow | None:
    """Return the reviewed contract row corresponding to an active F5V2 case."""
    reviewed_id = reviewed_id_for(case_id)
    return rows.get(reviewed_id) if reviewed_id else None


def contract_for(case_id: str, rows: dict[str, ReviewedGoldenRow]) -> str | None:
    row = row_for(case_id, rows)
    return row.ground_truth if row else None


def binding_errors(cases, rows: dict[str, ReviewedGoldenRow]) -> list[str]:
    """Detect disagreements that can be checked without pretending prose is executable evidence."""
    errors: list[str] = []
    for case in cases:
        reviewed_id = reviewed_id_for(case.id)
        if reviewed_id is None or reviewed_id not in rows:
            continue  # The v2 suite has additional safety cases; they remain JSON-native.
        row = rows[reviewed_id]
        # N/A means the reviewed row intentionally makes no domain assertion (common for attacks
        # that must be rejected before any knowledge-domain routing applies).
        if row.domain != "N/A" and row.domain != case.domain:
            errors.append(f"{case.id}: reviewed {reviewed_id} domain {row.domain!r} != {case.domain!r}")
        if case.expected_route and row.expected_route != case.expected_route:
            errors.append(f"{case.id}: reviewed {reviewed_id} route {row.expected_route!r} != {case.expected_route!r}")
    return errors
