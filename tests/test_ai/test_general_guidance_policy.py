"""Unit tests for `general_guidance_policy.narrow_policy` (F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md
§6.2/§6.3). Pins the monotonicity property (§6.2): `narrow_policy` may only map
`GENERAL_ALLOWED -> STRICT_INTERNAL`, never the reverse, over the full input cross-product.
"""

from __future__ import annotations

import itertools

import pytest

from src.ai.orchestration.general_guidance_policy import PolicySource, narrow_policy
from src.ai.orchestration.guidance_validation import GeneralKnowledgeConfig
from src.ai.orchestration.turn_interpreter import InterpreterRoute, KnowledgePolicy
from src.model.enums import DocumentDomain


def _config(**overrides) -> GeneralKnowledgeConfig:
    defaults = dict(enabled=True)
    defaults.update(overrides)
    return GeneralKnowledgeConfig(**defaults)


_ROUTES = (InterpreterRoute.KNOWLEDGE, InterpreterRoute.REUSE)
_DOMAINS = (DocumentDomain.PROJECT, DocumentDomain.POLICY)
_QUESTIONS = ("how do I install Python?", "how do I get VPN access for this project?")
_DEGRADED = (False, True)
_ENABLED = (False, True)
_PROPOSED = (KnowledgePolicy.STRICT_INTERNAL, KnowledgePolicy.GENERAL_ALLOWED)


@pytest.mark.parametrize(
    ("proposed", "route", "domain", "question", "degraded", "enabled"),
    list(itertools.product(_PROPOSED, _ROUTES, _DOMAINS, _QUESTIONS, _DEGRADED, _ENABLED)),
)
def test_monotone_narrowing_full_cross_product(
    proposed: KnowledgePolicy,
    route: InterpreterRoute,
    domain: DocumentDomain,
    question: str,
    degraded: bool,
    enabled: bool,
) -> None:
    """No input in the full cross-product ever yields GENERAL_ALLOWED when proposed was
    STRICT_INTERNAL -- the single property the whole design depends on (§6.2)."""
    effective, source = narrow_policy(
        proposed,
        route=route,
        knowledge_domain=domain,
        question=question,
        resolved_question=question,
        degraded=degraded,
        config=_config(enabled=enabled),
    )
    if proposed is KnowledgePolicy.STRICT_INTERNAL:
        assert effective is KnowledgePolicy.STRICT_INTERNAL
    assert isinstance(source, PolicySource)


def test_disabled_master_switch_narrows_regardless_of_everything_else() -> None:
    effective, source = narrow_policy(
        KnowledgePolicy.GENERAL_ALLOWED,
        route=InterpreterRoute.KNOWLEDGE,
        knowledge_domain=DocumentDomain.PROJECT,
        question="how do I install Python?",
        resolved_question="how do I install Python?",
        degraded=False,
        config=_config(enabled=False),
    )
    assert effective is KnowledgePolicy.STRICT_INTERNAL
    assert source is PolicySource.DISABLED


def test_degraded_verdict_narrows() -> None:
    effective, source = narrow_policy(
        KnowledgePolicy.GENERAL_ALLOWED,
        route=InterpreterRoute.KNOWLEDGE,
        knowledge_domain=DocumentDomain.PROJECT,
        question="how do I install Python?",
        resolved_question="how do I install Python?",
        degraded=True,
        config=_config(),
    )
    assert effective is KnowledgePolicy.STRICT_INTERNAL
    assert source is PolicySource.DEGRADED


def test_reuse_route_is_forced_route() -> None:
    effective, source = narrow_policy(
        KnowledgePolicy.GENERAL_ALLOWED,
        route=InterpreterRoute.REUSE,
        knowledge_domain=DocumentDomain.PROJECT,
        question="how do I install Python?",
        resolved_question="how do I install Python?",
        degraded=False,
        config=_config(),
    )
    assert effective is KnowledgePolicy.STRICT_INTERNAL
    assert source is PolicySource.FORCED_ROUTE


def test_policy_domain_is_forced_domain() -> None:
    effective, source = narrow_policy(
        KnowledgePolicy.GENERAL_ALLOWED,
        route=InterpreterRoute.KNOWLEDGE,
        knowledge_domain=DocumentDomain.POLICY,
        question="how do I install Python?",
        resolved_question="how do I install Python?",
        degraded=False,
        config=_config(),
    )
    assert effective is KnowledgePolicy.STRICT_INTERNAL
    assert source is PolicySource.FORCED_DOMAIN


@pytest.mark.parametrize(
    "question",
    [
        "how do I get VPN access for this project?",
        "how do I get vpn access?",
        "làm sao để cấp quyền admin cho tôi?",
        "who approves production deployments?",
        "how do I run rm -rf on the server?",
    ],
)
def test_sensitive_marker_forces_strict_internal(question: str) -> None:
    effective, source = narrow_policy(
        KnowledgePolicy.GENERAL_ALLOWED,
        route=InterpreterRoute.KNOWLEDGE,
        knowledge_domain=DocumentDomain.PROJECT,
        question=question,
        resolved_question="unrelated resolved subject",
        degraded=False,
        config=_config(),
    )
    assert effective is KnowledgePolicy.STRICT_INTERNAL
    assert source is PolicySource.FORCED_SENSITIVE


def test_sensitive_marker_checked_on_resolved_question_too() -> None:
    """§11.2: checking both question and resolved_question closes the gap where a benign-looking
    utterance resolves to a sensitive subject."""
    effective, source = narrow_policy(
        KnowledgePolicy.GENERAL_ALLOWED,
        route=InterpreterRoute.KNOWLEDGE,
        knowledge_domain=DocumentDomain.PROJECT,
        question="what about that?",
        resolved_question="how do I get VPN access for this project?",
        degraded=False,
        config=_config(),
    )
    assert effective is KnowledgePolicy.STRICT_INTERNAL
    assert source is PolicySource.FORCED_SENSITIVE


def test_generic_technical_question_is_honoured_as_general_allowed() -> None:
    effective, source = narrow_policy(
        KnowledgePolicy.GENERAL_ALLOWED,
        route=InterpreterRoute.KNOWLEDGE,
        knowledge_domain=DocumentDomain.PROJECT,
        question="how do I create a Python virtualenv?",
        resolved_question="how do I create a Python virtualenv?",
        degraded=False,
        config=_config(),
    )
    assert effective is KnowledgePolicy.GENERAL_ALLOWED
    assert source is PolicySource.INTERPRETER


def test_marker_set_is_closed_and_capped_at_40() -> None:
    from src.ai.orchestration.general_guidance_policy import _SENSITIVE_MARKERS

    assert len(_SENSITIVE_MARKERS) <= 40
