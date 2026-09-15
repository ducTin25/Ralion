"""Bot- and noise-detection for GitHub PR review corpora.

Ported unchanged from ``scripts/density_check.py`` (F6 gate R-1 tooling) so that
both the annotation script and any production PR-corpus consumer (F6 mining)
apply the exact same rule set — a single detection module, not two drifting
copies.
"""

from __future__ import annotations

import re

# GitHub App bot: login luôn kết thúc bằng "[bot]" — quy ước chuẩn của GitHub
# cho bot cài qua GitHub App (renovate[bot], dependabot[bot], netlify[bot]...).
#
# NHƯNG: nhiều bot lâu đời không dùng cơ chế GitHub App mà là account thường
# (classic token-based), nên KHÔNG có suffix "[bot]" — xác nhận thực nghiệm
# trên chính 2 dataset đang dùng: "bors" (292 comment, đứng đầu cargo),
# "rustbot"/"rfcbot" (cargo), "vue-bot" (70 comment, đồng hạng nhất vue).
# Suffix-check một mình sẽ bỏ sót toàn bộ nhóm này — đây chính là lý do cần
# một denylist tường minh, không suy đoán, cập nhật từ dữ liệu thật đã thấy.
#
# "copilot": tính năng GitHub Copilot code-review đăng review dưới display
# name "Copilot" (KHÔNG có suffix "[bot]") — xác nhận thực nghiệm trên
# thanos-io/thanos, PR #8792: 2 review_comment(diff) do "Copilot" viết,
# is_bot_comment=False, survived_filter=True trước khi vá. Đây là pattern
# bền vững ở cấp platform GitHub (không riêng thanos-io), sẽ tái xuất hiện
# ở bất kỳ repo/window nào bật tính năng này — hardcode giống bors/rustbot/
# vue-bot thay vì để --extra-bot-logins xử lý lại mỗi lần rerun.
KNOWN_NON_SUFFIX_BOTS = {"bors", "rustbot", "rfcbot", "vue-bot", "copilot"}


def is_bot(login: str, extra_bots: frozenset[str] = frozenset()) -> bool:
    if login.endswith("[bot]"):
        return True
    lowered = login.lower()
    return lowered in KNOWN_NON_SUFFIX_BOTS or lowered in extra_bots


NOISE_PHRASES = {
    "lgtm", "nice", "+1", "ok", "okay", "thanks", "thank you", "good catch",
    "nit", "sg", "sgtm", "approved", "cool", "great", "awesome", "yep", "yes",
    "done", "fixed", "good point",
}
EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002700-\U000027BF\U0001F600-\U0001F64F\U0001F680-\U0001F6FF]+"
)


def is_noise(body: str | None) -> bool:
    if not body:
        return True
    stripped = EMOJI_RE.sub("", body).strip()
    normalized = re.sub(r"[^\w\s+]", "", stripped).strip().lower()
    if not normalized:
        return True  # emoji-only
    if normalized in NOISE_PHRASES:
        return True
    word_count = len(normalized.split())
    if word_count < 10:
        return True
    return False
