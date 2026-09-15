"""Metric computation for the F5 evaluation suite (`EVAL_GUIDE.md` rubrics 1-9).

Split deliberately into two kinds of function:

- **Deterministic** -- computed from `ChatResult` and the golden case alone: retrieval metrics,
  citation integrity, the abstention outcome matrix, route accuracy, fallback-reason semantics,
  stability, forbidden-substring checks. These are the ones a Hard Gate may depend on, because
  they cannot drift with a judge model.
- **Judged** -- claim faithfulness and aspect coverage need a model to decide whether a claim is
  entailed by its evidence. Those live in `judge.py`; this module only aggregates their output.

`EVAL_GUIDE.md §15` is explicit that RAGAS must not decide ACL safety, route correctness,
fallback semantics, citation existence, latency, tokens or stability. Everything in that list is
computed here, deterministically, and never delegated to a judge.
"""

from __future__ import annotations

import math
import statistics
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from typing import Any, Iterable, Sequence

# ---------------------------------------------------------------------------------------
# Retrieval (EVAL_GUIDE.md §5)
#
# IMPORTANT SCOPE NOTE. The runner derives `retrieved_doc_ids` from `ChatResult.citations`,
# which is the ACCEPTED evidence set -- what survived the relevance gate, the evidence-sufficiency
# gate and `max_chunks_per_domain` -- not the raw candidate set the retrievers produced.
#
# So these are accepted-evidence metrics, and they are a LOWER BOUND on true retrieval recall: a
# document the retriever found but a gate dropped scores as a miss here. That is deliberate --
# it is the number that determines what the user can actually be told -- but it means a low value
# does NOT by itself prove a retrieval bug, and §5's candidate-level Recall@K is not what this
# computes. Candidate-level measurement needs the per-candidate rows recorded in
# `llm_call_logs.retrieval_scores` / `decision_details["gate_candidates"]`; see the coverage gaps
# in the run report.
# ---------------------------------------------------------------------------------------


def _rank_of_first_relevant(retrieved_doc_ids: Sequence[str], relevant: set[str]) -> int | None:
    """1-indexed rank of the first retrieved document that is one of the expected ones."""
    for index, doc_id in enumerate(retrieved_doc_ids, start=1):
        if doc_id in relevant:
            return index
    return None


def recall_at_k(retrieved_doc_ids: Sequence[str], relevant: set[str], k: int) -> float:
    """Fraction of expected documents present in the top-k.

    Document-level rather than chunk-level: a golden case names the document that must be
    reached, and which chunk of that document answers the question is a chunking decision the
    golden set deliberately does not pin (pinning chunk ids would make the fixture break on every
    re-chunk without any quality change).
    """
    if not relevant:
        return 0.0
    top = set(retrieved_doc_ids[:k])
    return len(top & relevant) / len(relevant)


def hit_at_k(retrieved_doc_ids: Sequence[str], relevant: set[str], k: int) -> bool:
    """Did ANY expected document appear in the top-k."""
    return bool(set(retrieved_doc_ids[:k]) & relevant)


def reciprocal_rank(retrieved_doc_ids: Sequence[str], relevant: set[str]) -> float:
    rank = _rank_of_first_relevant(retrieved_doc_ids, relevant)
    return 0.0 if rank is None else 1.0 / rank


def ndcg_at_k(retrieved_doc_ids: Sequence[str], relevant: set[str], k: int) -> float:
    """Binary-relevance nDCG@k.

    Binary, not graded: the golden schema records which documents are needed, not how strongly
    each contributes. Inventing graded relevance here would be fabricating a signal the fixture
    does not contain.
    """
    if not relevant:
        return 0.0
    dcg = sum(
        1.0 / math.log2(index + 1)
        for index, doc_id in enumerate(retrieved_doc_ids[:k], start=1)
        if doc_id in relevant
    )
    ideal = sum(1.0 / math.log2(index + 1) for index in range(1, min(len(relevant), k) + 1))
    return dcg / ideal if ideal else 0.0


def context_precision(retrieved_doc_ids: Sequence[str], relevant: set[str]) -> float:
    """Share of retrieved documents that are actually expected.

    Low precision with high recall means the answer was assembled from a noisy context, which
    `EVAL_GUIDE.md §5.1` says must not be scored as good retrieval.
    """
    if not retrieved_doc_ids:
        return 0.0
    return sum(1 for doc_id in retrieved_doc_ids if doc_id in relevant) / len(retrieved_doc_ids)


def context_recall(retrieved_doc_ids: Sequence[str], relevant: set[str]) -> float:
    """Share of expected documents that were retrieved at all (k unbounded)."""
    if not relevant:
        return 0.0
    return len(set(retrieved_doc_ids) & relevant) / len(relevant)


@dataclass(frozen=True)
class RetrievalMetrics:
    case_id: str
    retrieved: tuple[str, ...]
    relevant: tuple[str, ...]
    recall_at_5: float
    recall_at_10: float
    hit_at_5: bool
    hit_at_10: bool
    reciprocal_rank: float
    ndcg_at_10: float
    context_precision: float
    context_recall: float
    first_relevant_rank: int | None


def retrieval_metrics(
    case_id: str, retrieved_doc_ids: Sequence[str], relevant_doc_ids: Iterable[str]
) -> RetrievalMetrics:
    relevant = set(relevant_doc_ids)
    return RetrievalMetrics(
        case_id=case_id,
        retrieved=tuple(retrieved_doc_ids),
        relevant=tuple(sorted(relevant)),
        recall_at_5=recall_at_k(retrieved_doc_ids, relevant, 5),
        recall_at_10=recall_at_k(retrieved_doc_ids, relevant, 10),
        hit_at_5=hit_at_k(retrieved_doc_ids, relevant, 5),
        hit_at_10=hit_at_k(retrieved_doc_ids, relevant, 10),
        reciprocal_rank=reciprocal_rank(retrieved_doc_ids, relevant),
        ndcg_at_10=ndcg_at_k(retrieved_doc_ids, relevant, 10),
        context_precision=context_precision(retrieved_doc_ids, relevant),
        context_recall=context_recall(retrieved_doc_ids, relevant),
        first_relevant_rank=_rank_of_first_relevant(retrieved_doc_ids, relevant),
    )


# ---------------------------------------------------------------------------------------
# Citation integrity (EVAL_GUIDE.md §3.3, §12)
# ---------------------------------------------------------------------------------------


@dataclass(frozen=True)
class CitationIntegrity:
    total_citations: int
    resolvable: int
    unresolvable: tuple[str, ...]
    claims_total: int
    claims_without_citation: int
    fabricated: bool

    @property
    def validity(self) -> float:
        """Structural validity only.

        This is NOT `EVAL_GUIDE.md §3.3` Citation Validity in full: whether the cited evidence
        actually SUPPORTS the claim is a judgement, computed in judge.py and combined by the
        scorecard. What this measures is the half that must never be judged -- existence and
        membership of the accepted evidence set.
        """
        return 1.0 if not self.total_citations else self.resolvable / self.total_citations


def citation_integrity(result_citations: Sequence[dict], claims: Sequence[dict]) -> CitationIntegrity:
    """A citation is structurally valid when it names a real chunk of a real document.

    A claim citing a `chunk_id` absent from the answer's own citation set is the fabricated-
    citation failure the §12 Hard Gate forbids: the model produced a reference to evidence the
    server never accepted.
    """
    accepted_chunk_ids = {
        citation.get("chunk_id") for citation in result_citations if citation.get("chunk_id") is not None
    }
    unresolvable: list[str] = []
    total = 0
    resolvable = 0
    claims_without_citation = 0

    for citation in result_citations:
        total += 1
        if citation.get("chunk_id") is None or citation.get("document_id") is None:
            unresolvable.append(f"citation without chunk_id/document_id: {citation!r}"[:200])
        else:
            resolvable += 1

    for claim in claims:
        claim_citations = claim.get("citations") or []
        if not claim_citations:
            claims_without_citation += 1
            continue
        for citation in claim_citations:
            total += 1
            chunk_id = citation.get("chunk_id")
            if chunk_id is None or chunk_id not in accepted_chunk_ids:
                unresolvable.append(
                    f"claim {claim.get('claim_index')} cites chunk_id={chunk_id!r} "
                    "which is not in the accepted evidence set"
                )
            else:
                resolvable += 1

    return CitationIntegrity(
        total_citations=total,
        resolvable=resolvable,
        unresolvable=tuple(unresolvable),
        claims_total=len(claims),
        claims_without_citation=claims_without_citation,
        fabricated=bool(unresolvable),
    )


# ---------------------------------------------------------------------------------------
# Abstention outcome matrix (EVAL_GUIDE.md §6)
# ---------------------------------------------------------------------------------------

TRUE_ANSWER = "true_answer"
FALSE_REFUSAL = "false_refusal"
CORRECT_ABSTENTION = "correct_abstention"
FALSE_ANSWER = "false_answer"
PARTIAL_HONEST = "partial_honest"
PARTIAL_OVERCLAIM = "partial_overclaim"
SYSTEM_ERROR = "system_error"


def abstention_outcome(case_type: str, fell_back: bool, fallback_reason: str | None) -> str:
    """Classify one case into the §6 outcome matrix.

    `system_error` is kept as its own outcome rather than folded into a refusal: CLAUDE.md
    invariant 8 requires an infrastructure fault never to be counted as hallucination-avoidance,
    because doing so inflates the abstention rate with outages.
    """
    if fallback_reason == "system_error":
        return SYSTEM_ERROR
    if case_type == "answerable":
        return FALSE_REFUSAL if fell_back else TRUE_ANSWER
    if case_type == "unanswerable":
        return CORRECT_ABSTENTION if fell_back else FALSE_ANSWER
    if case_type == "partial":
        # A partial question may honestly stop only when evidence is genuinely unavailable or
        # insufficient.  Treating *every* fallback as honest hid scope/validator refusals on
        # answerable partial cases (POL-016): those are false refusals, not safe abstentions.
        # The content of a non-fallback partial answer is still judged separately for disclosure.
        if not fell_back:
            return PARTIAL_OVERCLAIM
        if fallback_reason in {"no_evidence", "insufficient_evidence"}:
            return PARTIAL_HONEST
        return FALSE_REFUSAL
    return TRUE_ANSWER if not fell_back else CORRECT_ABSTENTION


@dataclass
class AbstentionSummary:
    counts: Counter = field(default_factory=Counter)

    def add(self, outcome: str) -> None:
        self.counts[outcome] += 1

    @property
    def answerable_total(self) -> int:
        return self.counts[TRUE_ANSWER] + self.counts[FALSE_REFUSAL]

    @property
    def unanswerable_total(self) -> int:
        return self.counts[CORRECT_ABSTENTION] + self.counts[FALSE_ANSWER]

    @property
    def answerable_success_rate(self) -> float | None:
        return _ratio(self.counts[TRUE_ANSWER], self.answerable_total)

    @property
    def correct_abstention_rate(self) -> float | None:
        return _ratio(self.counts[CORRECT_ABSTENTION], self.unanswerable_total)

    @property
    def false_refusal_rate(self) -> float | None:
        return _ratio(self.counts[FALSE_REFUSAL], self.answerable_total)

    @property
    def false_answer_rate(self) -> float | None:
        return _ratio(self.counts[FALSE_ANSWER], self.unanswerable_total)


def _ratio(numerator: int, denominator: int) -> float | None:
    return None if denominator == 0 else numerator / denominator


# ---------------------------------------------------------------------------------------
# Routing (EVAL_GUIDE.md §7)
# ---------------------------------------------------------------------------------------


def route_accuracy(observed: Sequence[str | None], expected: Sequence[str | None]) -> float | None:
    """Accuracy over turns that actually declare an expected route."""
    graded = [(o, e) for o, e in zip(observed, expected) if e is not None]
    if not graded:
        return None
    return sum(1 for o, e in graded if o == e) / len(graded)


# ---------------------------------------------------------------------------------------
# Forbidden substrings (deterministic safety assertion)
# ---------------------------------------------------------------------------------------


def forbidden_hits(answer: str, forbidden: Iterable[str]) -> list[str]:
    """Case- and diacritic-form-insensitive containment check.

    NFC-normalised and case-folded so a forbidden marker cannot be evaded by a different Unicode
    composition of the same visible string.
    """
    haystack = unicodedata.normalize("NFC", answer).casefold()
    return [
        needle
        for needle in forbidden
        if unicodedata.normalize("NFC", needle).casefold() in haystack
    ]


# ---------------------------------------------------------------------------------------
# Stability (EVAL_GUIDE.md §9)
# ---------------------------------------------------------------------------------------


def jaccard(left: Iterable[Any], right: Iterable[Any]) -> float:
    left_set, right_set = set(left), set(right)
    if not left_set and not right_set:
        return 1.0
    if not left_set or not right_set:
        return 0.0
    return len(left_set & right_set) / len(left_set | right_set)


@dataclass(frozen=True)
class StabilityMetrics:
    case_id: str
    runs: int
    outcome_consistency: float
    route_consistency: float
    fallback_consistency: float
    evidence_jaccard_mean: float
    outcomes: tuple[str, ...]

    @property
    def is_stable(self) -> bool:
        return self.outcome_consistency >= 1.0


def stability_metrics(
    case_id: str,
    outcomes: Sequence[str],
    routes: Sequence[str | None],
    fallbacks: Sequence[str | None],
    evidence_sets: Sequence[Sequence[Any]],
) -> StabilityMetrics:
    """Consistency across N repeats of the same case.

    Consistency is measured as the share of runs agreeing with the MODAL value, not as
    agreement with the expected value -- a case that fails identically all five times is
    perfectly stable and separately wrong, and `EVAL_GUIDE.md §9` wants those two facts
    reported separately. Wording is deliberately never compared.
    """
    runs = len(outcomes)
    if runs == 0:
        return StabilityMetrics(case_id, 0, 0.0, 0.0, 0.0, 0.0, ())

    def modal_share(values: Sequence[Any]) -> float:
        counts = Counter(values)
        return counts.most_common(1)[0][1] / len(values) if values else 0.0

    pairwise = [
        jaccard(evidence_sets[i], evidence_sets[j])
        for i in range(len(evidence_sets))
        for j in range(i + 1, len(evidence_sets))
    ]
    return StabilityMetrics(
        case_id=case_id,
        runs=runs,
        outcome_consistency=modal_share(outcomes),
        route_consistency=modal_share(routes),
        fallback_consistency=modal_share(fallbacks),
        evidence_jaccard_mean=statistics.fmean(pairwise) if pairwise else 1.0,
        outcomes=tuple(outcomes),
    )


# ---------------------------------------------------------------------------------------
# Latency / tokens / cost (EVAL_GUIDE.md §10, §11)
# ---------------------------------------------------------------------------------------


def percentile(values: Sequence[float], fraction: float) -> float | None:
    """Nearest-rank percentile.

    Nearest-rank rather than interpolated: at the sample sizes this suite produces (roughly 140
    turns) an interpolated p99 is an invented number between two real observations, and
    `EVAL_GUIDE.md §10` wants measured latency reported honestly.
    """
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


@dataclass(frozen=True)
class LatencySummary:
    count: int
    p50: float | None
    p95: float | None
    p99: float | None
    mean: float | None
    maximum: float | None


def latency_summary(values: Sequence[float]) -> LatencySummary:
    return LatencySummary(
        count=len(values),
        p50=percentile(values, 0.50),
        p95=percentile(values, 0.95),
        p99=percentile(values, 0.99),
        mean=statistics.fmean(values) if values else None,
        maximum=max(values) if values else None,
    )


@dataclass(frozen=True)
class CostSummary:
    llm_calls: int
    prompt_tokens: int
    completion_tokens: int
    cost_estimate: float
    successful_tasks: int

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    @property
    def tokens_per_successful_task(self) -> float | None:
        return _ratio(self.total_tokens, self.successful_tasks)

    @property
    def cost_per_successful_task(self) -> float | None:
        if self.successful_tasks == 0:
            return None
        return self.cost_estimate / self.successful_tasks

    @property
    def llm_calls_per_turn(self) -> float | None:
        return None if self.llm_calls == 0 else self.llm_calls
