from langchain_openai import ChatOpenAI

from src.config import get_settings


def get_llm() -> ChatOpenAI:
    settings = get_settings()
    return ChatOpenAI(
        model=settings.model_name,
        api_key=settings.openai_api_key,
        temperature=settings.llm_temperature,
    )


def get_grounded_chat_llm() -> ChatOpenAI:
    """F5 is factual generation: sampling must stay deterministic."""
    settings = get_settings()
    if settings.openrouter_api_key:
        # OpenRouter expects provider-qualified OpenAI model ids. Keep the
        # direct OpenAI setting provider-neutral for the non-router path.
        router_model = settings.openrouter_model or (
            f"openai/{settings.model_name}"
            if settings.model_name.startswith("gpt-")
            else settings.model_name
        )
        return ChatOpenAI(
            model=router_model,
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_api_base,
            temperature=0,
        )
    return ChatOpenAI(model=settings.model_name, api_key=settings.openai_api_key, temperature=0)


def get_classifier_llm() -> ChatOpenAI:
    """DeepSeek — dùng riêng cho repo scanner AI classification fallback (Phase 3). DeepSeek expose
    API tương thích chuẩn OpenAI nên tái dùng thẳng ChatOpenAI, chỉ đổi base_url/model."""
    settings = get_settings()
    return ChatOpenAI(
        model="deepseek-chat",
        api_key=settings.deepseek_api_key,
        base_url="https://api.deepseek.com",
        temperature=0,
    )


def get_judge_llm() -> ChatOpenAI:
    """OpenAI (`gpt-4o-mini`) — judge model riêng cho Evaluation (scripts/eval_plan_content.py).

    `temperature=0`: chấm điểm cần ổn định, không cần đa dạng diễn đạt. Dùng OpenAI (khác hẳn
    DeepSeek/model sinh nội dung, và khác nhà cung cấp) để tránh self-preference bias khi model tự
    chấm bài do chính họ hàng model sinh ra (Day 14).

    Đã thử Groq (`openai/gpt-oss-120b` rồi `openai/gpt-oss-20b`) và Gemini trước — xem
    docs/PM/evaluation/plan-evaluation.md mục 1 và docs/PM/report-evaluation.md mục 7 cho toàn bộ
    quá trình + bug thật đã gặp (Groq free tier 429 chập chờn dù còn quota, và model "reasoning"
    đốt hết token vào suy luận nội bộ khiến `content` rỗng). Đổi sang OpenAI trả phí trực tiếp vì
    đơn giản/ổn định hơn, không cần `max_tokens` đặc biệt (không phải model reasoning ẩn).
    """
    settings = get_settings()
    return ChatOpenAI(
        model="gpt-4o-mini",
        api_key=settings.openai_api_key,
        temperature=0,
        timeout=60,
        max_retries=3,
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
