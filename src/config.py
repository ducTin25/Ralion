from functools import lru_cache
from typing import Literal

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SESSION_SECRET = "dev-only-session-secret-change-me"
# A valid (dev-only) Fernet key — base64.urlsafe_b64encode(b"\x00" * 32) — so the app still boots
# with a working (if insecure) encryptor before anyone sets a real key, mirroring how
# DEFAULT_SESSION_SECRET works below. Generate a real one with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
DEFAULT_GITHUB_CREDENTIAL_ENCRYPTION_KEY = "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA="


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # App
    app_name: str = "AI20K Agent"
    app_env: Literal["development", "production", "test"] = "development"
    app_port: int = Field(default=8000, ge=1, le=65535)
    app_host: str = "0.0.0.0"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"

    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    @property
    def cors_origin_list(self) -> list[str]:
        """Danh sách origin đã làm sạch — đây mới là thứ được nạp vào CORSMiddleware.

        Tách khỏi `cors_origins` thô vì AUDIT `F-27f`: một dòng `CORS_ORIGINS` bị xuống dòng
        trong `.env` từng biến giá trị thành `...,http://` — vừa mất origin cuối, vừa đăng ký
        một origin rác. Strip + loại phần tử rỗng để một lỗi định dạng không lặng lẽ trở thành
        cấu hình CORS sai, và bỏ trùng lặp nhưng giữ nguyên thứ tự khai báo.
        """
        seen: dict[str, None] = {}
        for raw in self.cors_origins.split(","):
            origin = raw.strip()
            if origin:
                seen.setdefault(origin, None)
        return list(seen)

    # Auth: khoá ký cookie phiên. Đổi khoá này sẽ vô hiệu mọi phiên đang mở.
    # Bắt buộc đặt trong .env ở production; mặc định chỉ dùng cho dev/test.
    session_secret: str = DEFAULT_SESSION_SECRET
    # Cho phép header X-User-Id thay cookie. Tiện khi gọi curl/Swagger lúc dev,
    # nhưng là lỗ hổng giả mạo danh tính nên phải tắt ở production.
    allow_header_user_context: bool = False

    # LLM
    openai_api_key: str = ""
    # Primary model for interactive chatbot generation.
    #
    # gpt-5-mini -> gpt-4o-mini on 2026-08-26, measured. gpt-5-mini is a REASONING model, and the
    # whole preceding round of work was spent making its reasoning cheap enough for an interactive
    # path (per-operation `reasoning_effort`, bigger timeouts, a bigger request budget). Measuring
    # the non-reasoning model instead made most of that moot -- it is faster at every stage AND at
    # least as accurate on everything measured:
    #
    #   stage             gpt-5-mini (tuned)        gpt-4o-mini
    #   turn_interpreter  8/8, p50 4468ms @ low     8/8, p50 1262ms, max 1870ms
    #   scope_gate        6/6, ~0.9-1.5ms @ minimal 10/10, max 1398ms  (4/4 attacks rejected)
    #   evidence_suff     4/4, 1069-1977ms          4/4, 1022ms on a 10-candidate prompt
    #   generation        3135-3652ms @ minimal     1388-1618ms
    #
    # The interpreter number is the decisive one: gpt-5-mini needed `reasoning_effort=low`
    # specifically because `minimal` mis-routed coreference follow-ups ("cái đó áp dụng từ khi
    # nào?" -> CONVERSATION 3/3). gpt-4o-mini gets that same case right with no reasoning at all,
    # which is the whole justification for the 8.0s interpreter timeout disappearing.
    #
    # `_supports_reasoning_effort` in the completion adapter returns False for this family, so the
    # entire per-operation reasoning map goes inert on its own -- no code path needs to know the
    # model changed. Switching back to a gpt-5/o-series model re-arms it automatically, which is
    # why that map and its measurements are kept rather than deleted.
    #
    # NOT re-validated: RAGAS faithfulness / the guardrail fixture have not been re-run on this
    # model in this configuration. The spot checks above are spot checks (CLAUDE.md §9 wants the
    # harness for a model change) -- see CHANGE_LOG.md.
    # Live UX validation baseline: Luna with reasoning explicitly disabled.
    model_name: str = "gpt-5.6-luna"
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    # 900 -> 2048 on 2026-08-23 (BGK live testing): this is the shared max_tokens ceiling for
    # EVERY chat LLM call (turn_interpreter, scope_gate, evidence_sufficiency_gate, and
    # AnswerGenerator all share one ChatOpenAI provider -- src/infrastructure/ai/resources.py).
    # BGK's v3 prompt explicitly asks general_guidance for concrete, step-by-step detail when the
    # user requests it; 900 tokens was observed live to truncate the JSON mid-response on exactly
    # that kind of answer, producing a response that reads as cut off mid-sentence (see
    # CHANGE_LOG.md). Raising the ceiling costs nothing on the short single-word/JSON-verdict
    # gates (it is a ceiling, not a target) and only lets AnswerGenerator's genuinely longer
    # answers finish instead of truncating.
    chat_max_output_tokens: int = Field(default=2048, ge=64, le=4096)
    # F5 audit 2026-08-30 (BGK structured-output reliability, Thread C follow-up): the shared
    # ceiling above is sized for the whole pool it serves (turn_interpreter/scope_gate/
    # evidence_sufficiency_gate's short single-verdict calls included), so raising it further for
    # everyone re-provisions cheap calls that never needed the room. AnswerGenerator gets its own,
    # higher ceiling instead -- same 2026-08-23 truncation failure mode (`chat_max_output_tokens`'s
    # own comment above), but isolated to the one call shape that actually needs it: a genuinely
    # detailed BGK guidance answer, restructured into multiple `guidance_item_max_chars`-bounded
    # items under repair, can still exceed 2048 tokens before the reasoning-model's hidden
    # reasoning-token overhead is even counted. `0` (falsy) means "not configured" and falls back
    # to `chat_max_output_tokens` -- same idiom as `openrouter_model or model_name` below.
    answer_generator_max_output_tokens: int = Field(default=4096, ge=0, le=8192)
    # 2026-08-26, measured. `model_name` above is a REASONING model, and nothing was setting
    # `reasoning_effort`, so every call defaulted to `medium`. Measured on the live provider for
    # one `turn_interpreter` verdict ("tôi mệt quá", 6450-token prompt, 5888 of it cached):
    # 12615 ms with 960 reasoning_tokens behind ~68 tokens of visible JSON. 93% of the completion
    # was invisible reasoning. That, not prompt size and not network, is where the interactive
    # budget was going: three judges at ~3s each, every one of them silently blowing it. The
    # `turn_interpreter` fails OPEN, so the symptom was not an error but Phase 2 routing quietly
    # reverting to KNOWLEDGE on 16% of real turns (llm_call_logs, 2026-08-25).
    #
    # The EFFORT PER OPERATION lives in `openai_completion_adapter._REASONING_EFFORT_BY_OPERATION`,
    # not here, because each value is tied to a specific measurement documented beside it -- and
    # they are not the same value: `minimal` was measured to MIS-ROUTE coreference follow-ups, so
    # the interpreter needs `low`. This key is only the master switch.
    #
    # `False` restores the provider default everywhere, a config-only rollback with no code change.
    chat_reasoning_effort_enabled: bool = True
    # Overrides the per-operation defaults when set. `none` is intentional for the current live
    # UX measurement; it prevents Luna falling back to its provider default of `medium`.
    chat_reasoning_effort_override: Literal[
        "none", "minimal", "low", "medium", "high", "xhigh", "max"
    ] | None = "none"

    # DeepSeek (repo scanner AI classification fallback — Phase 3; sinh nội dung Candidate Plan — Phase 4)
    deepseek_api_key: str = ""
    deepseek_classifier_timeout_seconds: float = Field(default=20.0, gt=0.0)
    deepseek_classifier_max_concurrency: int = Field(default=4, ge=1, le=16)

    # Phase 4 — bật/tắt bước sinh nội dung bằng AI. Tắt (hoặc thiếu deepseek_api_key) thì pipeline
    # chạy baseline B0 deterministic, vẫn ra plan đầy đủ — dùng cho test/CI và để đo AI vs baseline.
    plan_generation_use_ai: bool = True

    # Đơn giá DeepSeek (USD / 1 TRIỆU token) để tự tính chi phí 1 lượt sinh plan. Vì sao cần: model
    # được gọi qua `base_url` riêng của DeepSeek, Langfuse không có sẵn bảng giá cho nó nên cột cost
    # trên dashboard hiện 0 dù token đếm đúng. Có 2 số này thì log tự tính ra tiền thật, không phải
    # ngồi nhân tay. Cập nhật khi nhà cung cấp đổi giá — để ở config chứ không hardcode trong code.
    deepseek_input_usd_per_mtok: float = 0.27
    deepseek_output_usd_per_mtok: float = 1.10

    # Langfuse (observability cho pipeline sinh plan — Phase 4). Thiếu key = no-op, không chặn dev/CI.
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    # OpenRouter is OpenAI-compatible and is preferred by F5 when configured.
    openrouter_api_key: str = ""
    openrouter_api_base: str = "https://openrouter.ai/api/v1"
    openrouter_model: str = ""

    # Groq — judge model riêng cho Evaluation (docs/PM/evaluation/plan-evaluation.md). Endpoint
    # tương thích OpenAI, dùng cho scripts/eval_plan_content.py. Cố tình KHÁC provider với DeepSeek
    # (model sinh nội dung) để tránh self-preference bias khi chấm điểm (Day 14).
    groq_api_key: str = ""
    groq_api_base: str = "https://api.groq.com/openai/v1"
    # `openai/gpt-oss-120b` ban đầu chọn (plan-evaluation.md mục 1) nhưng đo thật lúc chạy pilot bị
    # 429 dồn dập ngay cả khi header báo còn dư quota — kể cả gọi trực tiếp bằng curl, không phải
    # lỗi script (bằng chứng: Groq dashboard/logs, request 429 có latency=0, tokens=0 — bị chặn
    # ngay từ tầng hạ tầng `on_demand`, không phải hết ngân sách). Đổi sang `openai/gpt-oss-20b`
    # (cùng họ, cùng key, không cần key mới) — test thật 15/15 request liên tiếp đều 200 OK.
    groq_judge_model: str = "openai/gpt-oss-20b"

    # Remote BGE-M3 service (Modal).  When configured, this is used for both
    # ingestion and retrieval so every vector stays in the same 1024d space.
    bge_m3_endpoint: str = ""
    bge_m3_api_key: str = ""

    # F5 operational reliability. These are hard safety budgets, not product latency SLOs.
    # Sized from the measured stage caps, 2026-08-26. A budget smaller than the sum of the caps
    # does not make a turn faster -- it decides in advance which stage gets starved, and since
    # generation runs LAST the starved one is always the call that writes the answer (trace
    # 72e4e5ed: generation got 10s of a 20s budget, needed 15-17s, returned `system_error`).
    #
    # After (a) running the guardrail concurrently with the interpreter, and (b) moving to
    # gpt-4o-mini, every stage is ~1-2s:
    #
    #   scope_gate  +  turn_interpreter   4.0s   CONCURRENT -> the LONGER of the two, not the sum
    #   evidence_sufficiency_gate         4.0s
    #   generation                       ~2.0s   (measured 1388-1618ms)
    #                                    -----
    #   worst-case caps                  10.0s + generation, inside 17.0s
    #
    # Measured end-to-end LLM time for a real KNOWLEDGE turn fell from ~20.4s (before this work)
    # to ~6.9s on tuned gpt-5-mini; this model is expected lower again, and is re-measured live
    # after the switch rather than projected.
    # The interpreter increase from 4s to 6s also raises the concurrent judge block from 4s to
    # 6s. Keep 6.5s available for measured steady-state generation after that block plus ESG;
    # embedding + LLM + persistence still fit exactly inside the wall-clock ceiling.
    chat_overall_deadline_seconds: float = Field(default=24.0, gt=0.0)
    chat_embedding_budget_seconds: float = Field(default=6.0, gt=0.0)
    chat_llm_budget_seconds: float = Field(default=17.0, gt=0.0)
    chat_persistence_reserve_seconds: float = Field(default=1.0, ge=0.0)
    # Idle keep-alive window for the chat-side httpx pools.  httpx defaults to 5s, which is
    # shorter than the gap between two chat turns, so in practice every chat request paid a
    # fresh TCP+TLS handshake to Modal.  Measured against the deployed BGE-M3 endpoint:
    # handshake 562ms median (609ms max), embed call 1547ms on a fresh connection vs 688-828ms
    # on a reused one, still ~700ms after 60s idle once the connection is actually held.
    chat_http_keepalive_expiry_seconds: float = Field(default=300.0, gt=0.0)
    # Sized from the same measurement, not guessed: connect covers the 562ms handshake with
    # room for jitter (0.75s left only ~140ms of margin and was the timeout that fired), read
    # covers ~1s of server-side embed compute with the same kind of headroom.
    chat_embedding_connect_timeout_seconds: float = Field(default=2.0, gt=0.0)
    chat_embedding_read_timeout_seconds: float = Field(default=3.0, gt=0.0)
    chat_embedding_max_attempts: int = Field(default=2, ge=1, le=2)
    chat_embedding_backoff_initial_seconds: float = Field(default=0.05, ge=0.0)
    chat_embedding_backoff_multiplier: float = Field(default=2.0, ge=1.0)
    chat_embedding_backoff_max_seconds: float = Field(default=0.2, ge=0.0)
    chat_llm_connect_timeout_seconds: float = Field(default=2.0, gt=0.0)
    chat_llm_read_timeout_seconds: float = Field(default=15.0, gt=0.0)
    chat_llm_max_attempts: int = Field(default=2, ge=1, le=2)
    chat_llm_backoff_initial_seconds: float = Field(default=0.1, ge=0.0)
    chat_llm_backoff_multiplier: float = Field(default=2.0, ge=1.0)
    chat_llm_backoff_max_seconds: float = Field(default=0.5, ge=0.0)
    # The Modal deployment scales to zero to stay within the Starter credit, so any endpoint
    # that embeds (chat, PM/HR document upload, GitHub sync) pays a ~41s cold start after
    # SCALEDOWN_WINDOW_SECONDS idle. Ping on an interval shorter than that window so every
    # embedding-dependent use case sees a warm container, not just chat's own retry budget.
    chat_embedding_warmup_enabled: bool = Field(default=True)
    chat_embedding_warmup_interval_seconds: float = Field(default=240.0, gt=0.0)
    chat_embedding_warmup_timeout_seconds: float = Field(default=60.0, gt=0.0)
    # RC-1 (interpreter cold start). Same class of problem as the embedding pool above, on the
    # LLM pool: with an empty pool the first turn pays TCP+TLS to the provider *inside* the
    # interpreter's own timeout. Measured on trace1984 and its cohort: interpreter TimeoutError
    # clusters at the first interpreted turn (turn_index 0: 96 occurrences, 1: 8, later turns: 2
    # combined), and `scope_and_interpret` averages 2748ms/2716ms at turns 0-1 against 1141-1589ms
    # from turn 2 on -- with chat_llm_connect_timeout_seconds=2.0 the handshake alone consumed a
    # material part of the old 4s interpreter budget. This ping opens a pooled connection and keeps it inside
    # chat_http_keepalive_expiry_seconds, so no chat turn pays the handshake. It is an HTTP GET on
    # the provider base URL, NOT a completion: it mints no tokens and is therefore not an LLM call
    # that invariant 10 would require in `llm_call_logs`.
    chat_llm_warmup_enabled: bool = Field(default=True)
    chat_llm_warmup_interval_seconds: float = Field(default=240.0, gt=0.0)
    chat_llm_warmup_timeout_seconds: float = Field(default=10.0, gt=0.0)
    # F-22 chat budget guard: in-process request rate limit + daily usage/cost caps, read from
    # llm_call_logs (no new store). 0 disables the corresponding cap/limit.
    chat_rate_limit_max_requests: int = Field(default=10, ge=0)
    chat_rate_limit_window_seconds: float = Field(default=60.0, gt=0.0)
    chat_daily_request_cap_per_user: int = Field(default=200, ge=0)
    chat_daily_cost_cap_usd_per_user: float = Field(default=2.0, ge=0.0)
    chat_daily_cost_cap_usd_per_project: float = Field(default=10.0, ge=0.0)
    chat_cost_per_1k_prompt_tokens_usd: float = Field(default=0.00015, ge=0.0)
    chat_cost_per_1k_completion_tokens_usd: float = Field(default=0.0006, ge=0.0)

    # F6 Scheduled Incremental Convention Discovery — in-process scheduler poll interval
    # (src/infrastructure/scheduling/convention_discovery_scheduler.py). No Redis/Celery: a
    # single-process uvicorn deployment (no --workers) makes an asyncio loop safe here.
    convention_discovery_poll_seconds: float = Field(default=60.0, gt=0.0)

    ingestion_overall_deadline_seconds: float = Field(default=600.0, gt=0.0)
    ingestion_embedding_connect_timeout_seconds: float = Field(default=5.0, gt=0.0)
    ingestion_embedding_read_timeout_seconds: float = Field(default=120.0, gt=0.0)
    ingestion_embedding_max_attempts: int = Field(default=4, ge=1)
    ingestion_embedding_backoff_initial_seconds: float = Field(default=1.0, ge=0.0)
    ingestion_embedding_backoff_multiplier: float = Field(default=3.0, ge=1.0)
    ingestion_embedding_backoff_max_seconds: float = Field(default=9.0, ge=0.0)

    # Dev/test-only fallback GitHub PAT. Production project sync resolves a per-project,
    # encrypted credential connected via PATCH /knowledge-documents/pm/projects/{id}/github-repo
    # (see github_credential_provider.py) — this global token is never used there. It only
    # exists so local dev/CI can sync a single test repo without connecting a credential first.
    # The PAT itself must have Contents: Read-only regardless of which path uses it.
    github_token: str = ""
    # Fernet key encrypting `project_github_credentials.token_ciphertext` at rest. Must be
    # explicitly configured in production, same discipline as session_secret below.
    github_credential_encryption_key: str = DEFAULT_GITHUB_CREDENTIAL_ENCRYPTION_KEY

    # Database
    database_url: str = "postgresql+asyncpg://app:app@localhost:5433/pgonboarding"

    # Cloudinary (object storage cho KnowledgeDocument)
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # HR upload tài liệu chính sách
    # Web server không nạp BGE-M3 local: production gọi Modal qua BGE_M3_ENDPOINT.
    # Bật cờ này để dev/test chạy được toàn bộ luồng mà không gọi remote service.
    use_fake_embedder: bool = True
    # Ingest chạy đồng bộ trong request nên phải chặn file quá lớn, tránh treo worker.
    max_policy_upload_mb: int = 10

    @model_validator(mode="after")
    def validate_production_auth(self) -> "Settings":
        has_endpoint = bool(self.bge_m3_endpoint)
        has_api_key = bool(self.bge_m3_api_key)
        if has_endpoint != has_api_key:
            raise ValueError("BGE_M3_ENDPOINT and BGE_M3_API_KEY must be configured together")
        if self.use_fake_embedder and (has_endpoint or has_api_key):
            raise ValueError("USE_FAKE_EMBEDDER cannot be combined with BGE-M3 remote configuration")
        if not self.use_fake_embedder and not (has_endpoint and has_api_key):
            raise ValueError("BGE-M3 remote configuration is required when USE_FAKE_EMBEDDER is false")
        has_langfuse_public = bool(self.langfuse_public_key)
        has_langfuse_secret = bool(self.langfuse_secret_key)
        if has_langfuse_public != has_langfuse_secret:
            raise ValueError("LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY must be configured together")
        if has_langfuse_public and not self.langfuse_host.startswith("https://"):
            raise ValueError("LANGFUSE_HOST must use HTTPS when Langfuse is enabled")
        if self.app_env != "production":
            return self
        if self.allow_header_user_context:
            raise ValueError("ALLOW_HEADER_USER_CONTEXT must be false in production")
        if self.session_secret == DEFAULT_SESSION_SECRET:
            raise ValueError("SESSION_SECRET must be explicitly configured in production")
        if self.github_credential_encryption_key == DEFAULT_GITHUB_CREDENTIAL_ENCRYPTION_KEY:
            raise ValueError("GITHUB_CREDENTIAL_ENCRYPTION_KEY must be explicitly configured in production")
        if self.use_fake_embedder:
            raise ValueError("USE_FAKE_EMBEDDER must be false in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
