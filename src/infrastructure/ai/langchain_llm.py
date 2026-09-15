from langchain_openai import ChatOpenAI

from src.config import get_settings


def get_llm() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        temperature=settings.llm_temperature,
    )


def get_classifier_llm() -> ChatOpenAI:
    """DeepSeek — dùng riêng cho repo scanner AI classification fallback (Phase 3). DeepSeek expose
    API tương thích chuẩn OpenAI nên tái dùng thẳng ChatOpenAI, chỉ đổi base_url/model."""
    settings = get_settings()
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
        temperature=0,
        timeout=settings.deepseek_classifier_timeout_seconds,
        max_retries=1,
    )


def get_rule_mining_llm() -> ChatOpenAI:
    """GPT-5 mini via direct OpenAI API — F6 RuleMiningWorker structured extraction
    (F6_RULE_MINING_SPEC.md §4.2 step 3).

    2026-08-20 Phase 7 patch: switched from OpenRouter to direct OpenAI
    (`settings.openai_api_key`) — the OpenRouter account's credit balance hit 0 mid Phase 7
    e2e run (see CHANGE_LOG.md); the project added a direct OpenAI key instead of topping up
    OpenRouter. Model id has no provider prefix here ("gpt-5-mini", not "openai/gpt-5-mini")
    because direct OpenAI doesn't use OpenRouter's provider-prefixed ids — verified against the
    real API before switching (200 OK, `model: gpt-5-mini-2025-08-07`).

    `max_tokens=3000`: GPT-5 mini is a reasoning model — it spends hidden reasoning tokens
    before the visible JSON output (measured directly on OpenAI, not just OpenRouter: ~128
    reasoning tokens even for a trivial reply). 3000 leaves headroom for reasoning + a short
    JSON object while keeping cost/request bounded — a one-sentence rule_text_draft and a short
    rationale never need more than that.
    `temperature=0`: this is a classification+normalization task (evidence_type/reuse_scope
    are fixed labels, rule_text_draft must be a stable paraphrase), same discipline as
    `get_classifier_llm` above, not free generation like `get_plan_content_llm`.
    `timeout=120, max_retries=2`: this runs from a background worker over a PR corpus, not
    the interactive chat path — CLAUDE.md's Phase 5/F-06 distinction requires a patient
    policy here, the opposite of chat's ~1.5s budget. No tools are bound to this client —
    the mining pipeline invariant (§0) forbids tool-calling for this LLM call.
    """
    settings = get_settings()
    api_key = settings.openai_api_key
    if settings.app_env == "test" and not api_key:
        api_key = "test-only-placeholder"
    return ChatOpenAI(
        model="gpt-5-mini",
        api_key=api_key,
        temperature=0,
        max_tokens=3000,
        timeout=120,
        max_retries=2,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def get_plan_content_llm() -> ChatOpenAI:
    """DeepSeek — sinh nội dung PlanTask (Phase 4, bước 5).

    `temperature=0.2`: cần bám sát tài liệu (thấp) nhưng vẫn diễn đạt tự nhiên được, khác với
    classifier ở trên vốn chỉ chọn nhãn nên để 0 tuyệt đối.
    Dùng DeepSeek chứ không OpenAI vì rẻ hơn ~10x cho cùng khối lượng, và để giữ OpenAI làm judge
    độc lập ở bước eval (tránh self-preference bias khi model tự chấm bài mình — Day 14).
    """
    settings = get_settings()
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
        temperature=0.2,
        timeout=60,
        max_retries=1,
    )
