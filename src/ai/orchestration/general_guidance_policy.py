"""Server-side narrowing of `KnowledgePolicy` -- pure, no I/O, no LLM, no DB.

F5_BOUNDED_GENERAL_KNOWLEDGE_SPEC.md §6.2/§6.3. `narrow_policy` is a monotone narrowing
operator with `STRICT_INTERNAL` absorbing: it may only map `GENERAL_ALLOWED -> STRICT_INTERNAL`,
never the reverse. There is no input under which it returns `GENERAL_ALLOWED` when `proposed`
was `STRICT_INTERNAL` -- pinned by `tests/test_ai/test_general_guidance_policy.py`.

§6.3 is normative and binding: the `TurnInterpreter` is the primary -- and the only *semantic* --
eligibility classifier. The sensitive-marker denylist below is a defence-in-depth backstop, not a
routing system: it can only narrow, is closed and capped at 40 entries, and must never grow
per-marker messaging/categories/scoring. A non-zero `FORCED_SENSITIVE` rate in production is a
defect signal (the interpreter is missing a class of question), never a normal operating mode --
see §15.2 G3, which requires every §11.2 fixture case to be caught by the interpreter *alone*,
with this denylist disabled.
"""

from __future__ import annotations

import enum
import re
import unicodedata

from src.ai.orchestration.guidance_validation import GeneralKnowledgeConfig
from src.ai.orchestration.turn_interpreter import InterpreterRoute, KnowledgePolicy
from src.model.enums import DocumentDomain


class PolicySource(enum.StrEnum):
    INTERPRETER = "interpreter"  # the interpreter's own verdict, honoured unmodified
    DISABLED = "disabled"  # chat.general_knowledge.enabled is false (master switch)
    DEGRADED = "degraded"  # malformed/errored/sanitized verdict, or an unparseable field
    FORCED_ROUTE = "forced_route"  # route is not KNOWLEDGE (e.g. REUSE, §12.2)
    FORCED_DOMAIN = "forced_domain"  # knowledge_domain is POLICY (§11.1)
    FORCED_SENSITIVE = "forced_sensitive"  # defence-in-depth marker hit (§11.2)


_COMBINING = re.compile(r"[̀-ͯ]")  # Unicode combining diacritical marks block


def _diacritic_folded(text: str) -> str:
    text = text.casefold().replace("đ", "d").replace("Đ", "d")
    return _COMBINING.sub("", unicodedata.normalize("NFD", text))


# §6.3 rule 2: closed, capped at 40. §6.3 rule 3: every addition here must be paired with an
# interpreter fixture (`TI-*`) proving the interpreter now also classifies the case
# STRICT_INTERNAL on its own -- a marker added without that fix is architectural debt.
_SENSITIVE_MARKERS: tuple[str, ...] = (
    # credentials / tokens / secrets / keys / VPN (§11.2 row 1)
    "vpn access",
    "vpn",
    "api key",
    "api keys",
    "ssh key",
    "ssh keys",
    "access token",
    "credentials",
    "password",
    "secret key",
    "mat khau",
    "khoa api",
    # access grants / permissions / roles / onboarding to a system (§11.2 row 2)
    "grant access",
    "admin access",
    "production access",
    "add me as admin",
    "cap quyen",
    "quyen admin",
    "quyen truy cap he thong",
    # production deployment / release / rollback / migration on an environment (§11.2 row 3)
    "deploy to production",
    "production deployment",
    "rollback production",
    "migrate production",
    "release to production",
    "trien khai len production",
    # destructive operations (§11.2 row 4)
    "drop table",
    "rm -rf",
    "force-push",
    "force push",
    "reset --hard",
    "truncate table",
    # ownership / approval (§11.2 row 5)
    "who owns",
    "who approves",
    "ai duyet",
    "ai chiu trach nhiem",
)
assert len(_SENSITIVE_MARKERS) <= 40, "§6.3 rule 2: sensitive marker set is capped at 40"

_FOLDED_SENSITIVE_MARKERS: tuple[str, ...] = tuple(
    _diacritic_folded(marker) for marker in _SENSITIVE_MARKERS
)


def _sensitive_marker_hit(text: str) -> bool:
    folded = _diacritic_folded(text)
    return any(
        re.search(r"(?<!\w)" + re.escape(marker) + r"(?!\w)", folded)
        for marker in _FOLDED_SENSITIVE_MARKERS
    )


def narrow_policy(
    proposed: KnowledgePolicy,
    *,
    route: InterpreterRoute,
    knowledge_domain: DocumentDomain,
    question: str,
    resolved_question: str,
    degraded: bool,
    config: GeneralKnowledgeConfig,
) -> tuple[KnowledgePolicy, PolicySource]:
    """§6.2. `degraded` is the caller-computed
    `verdict.malformed or verdict.errored or verdict.sanitized or verdict.knowledge_policy_degraded`
    (§5.1) -- passed in rather than re-derived here so this stays a pure function of primitives,
    with no `InterpreterVerdict` import/dependency.

    Checks both `question` (the raw current utterance) and `resolved_question` (§11.2: "checking
    both closes the gap where a benign-looking utterance resolves to a sensitive subject, or the
    reverse").
    """
    if not config.enabled:
        return KnowledgePolicy.STRICT_INTERNAL, PolicySource.DISABLED
    if degraded:
        return KnowledgePolicy.STRICT_INTERNAL, PolicySource.DEGRADED
    if route is not InterpreterRoute.KNOWLEDGE:
        return KnowledgePolicy.STRICT_INTERNAL, PolicySource.FORCED_ROUTE
    if knowledge_domain is DocumentDomain.POLICY:
        return KnowledgePolicy.STRICT_INTERNAL, PolicySource.FORCED_DOMAIN
    if _sensitive_marker_hit(question) or _sensitive_marker_hit(resolved_question):
        return KnowledgePolicy.STRICT_INTERNAL, PolicySource.FORCED_SENSITIVE
    return proposed, PolicySource.INTERPRETER
