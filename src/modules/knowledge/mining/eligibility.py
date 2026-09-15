"""F6_RULE_MINING_SPEC.md §5.3 — the eligibility guardrail, enforced at the query layer, not
baked into the clustering algorithm (SPEC §4.2 step 6 / CLAUDE.md Phase 5 §5): a connected
component of >=2 nodes from the same PR (two evidence units in one PR that happen to read
alike) must NOT become a RuleFamily. Clustering stays blind to PR distribution; this module
is the separate, later check.

Deliberately no `COUNT(DISTINCT re.author) >= 2` condition — removed on purpose per SPEC §2.1/
§2.2, not an oversight.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.model.enums import RuleEvidenceType

# Literal translation of F6_RULE_MINING_SPEC.md §5.3's SQL — same tables, same WHERE/GROUP
# BY/HAVING, only column names adapted to the real schema (rc.id -> rc.rule_candidate_id; the
# SPEC's `rule_evidence`/`rule_candidate` are this schema's `rule_evidences`/`rule_candidates`).
_ELIGIBLE_FAMILY_IDS_SQL = text(
    """
    SELECT re.rule_family_id AS rule_family_id
    FROM rule_evidences re
    JOIN rule_candidates rc ON re.rule_candidate_id = rc.rule_candidate_id
    WHERE rc.evidence_type IN (:reusable_correction, :convention)
      AND rc.reuse_scope >= 1
    GROUP BY re.rule_family_id
    HAVING COUNT(DISTINCT re.evidence_unit_id) >= 2
       AND COUNT(DISTINCT re.pr_number) >= 2
    """
)


async def select_eligible_family_ids(session: AsyncSession) -> set[int]:
    result = await session.execute(
        _ELIGIBLE_FAMILY_IDS_SQL,
        {
            "reusable_correction": RuleEvidenceType.REUSABLE_CORRECTION.value,
            "convention": RuleEvidenceType.CONVENTION.value,
        },
    )
    return {row.rule_family_id for row in result}


async def prune_ineligible_families(session: AsyncSession, candidate_family_ids: set[int]) -> set[int]:
    """candidate_family_ids: the RuleFamily rows this mining run just created (speculatively,
    from every >=2-node connected component). Deletes any of them not eligible per the query
    above, and their member RuleEvidence rows. Never touches a RuleFamily outside this set —
    scoped to the current run, not a global re-check of every family ever mined."""
    from sqlalchemy import delete

    from src.model.rule_evidence import RuleEvidence
    from src.model.rule_family import RuleFamily

    if not candidate_family_ids:
        return set()
    eligible = await select_eligible_family_ids(session)
    ineligible = candidate_family_ids - eligible
    if not ineligible:
        return set()

    await session.execute(delete(RuleEvidence).where(RuleEvidence.rule_family_id.in_(ineligible)))
    await session.execute(delete(RuleFamily).where(RuleFamily.rule_family_id.in_(ineligible)))
    await session.commit()
    return ineligible
