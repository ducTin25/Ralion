"""Prompt builder + response parser thuần (không gọi LLM) cho scripts/eval_plan_content.py.

Tách riêng khỏi eval_plan_content.py để test được bằng pytest thường (không cần mock mạng, không
cần key thật) — đúng nguyên tắc đã áp dụng cho content_llm.py (tách phần "gọi LLM" khỏi phần "xây
prompt/đọc kết quả"). Xem docs/PM/evaluation/plan-evaluation.md mục 5 cho công thức từng metric.
"""

from __future__ import annotations

import json
import re

JUDGE_CRITERIA = ("correctness", "relevance", "completeness", "coherence")

# Groq free tier trần 8000 token/phút (đo thật khi chạy pilot — 1-câu-hỏi-1-lời-gọi cho case
# COMPANY (70 chunk) tự nó đã vượt trần chỉ với 1 case). Gộp nhiều câu hỏi/chunk vào 1 lời gọi để
# giảm SỐ LỜI GỌI, nhưng vẫn phải giới hạn số phần tử/lô để 1 lời gọi không tự nó vượt trần — cùng
# tinh thần với `content_llm.MAX_CHUNKS_PER_BATCH`.
#
# 20 (không phải 6): batch nhỏ hơn buộc gửi LẠI TOÀN BỘ nguồn tài liệu (source_text) nhiều lần —
# chính phần lặp lại đó, không phải câu hỏi, mới là phần tốn token nhất (đo thật lúc pilot: 1 case
# ~10 chunk vẫn 429 dù đã gộp batch=6, vì source_text bị gửi lại 2-3 lần). Batch=20 đủ để hầu hết
# case gửi nguồn CHỈ 1 LẦN — kết hợp với việc cắt ngắn nguồn ở `eval_plan_content._cap_chunks_for_
# judge` (giới hạn riêng, xem file đó) để 1 lời gọi không tự vượt trần.
MAX_ITEMS_PER_JUDGE_BATCH = 20


def build_extract_claims_prompt(text: str) -> str:
    return (
        "Tách đoạn văn sau thành các câu khẳng định độc lập, mỗi câu 1 dòng, không diễn giải "
        "thêm, không đánh số, không thêm gạch đầu dòng.\n\n"
        f"ĐOẠN VĂN:\n{text}"
    )


def parse_claims_response(response_text: str) -> list[str]:
    """1 dòng = 1 claim. Bỏ dòng rỗng và ký tự đánh số/gạch đầu dòng còn sót nếu model không theo
    đúng chỉ dẫn."""
    claims = []
    for line in response_text.splitlines():
        cleaned = line.strip().lstrip("-•*").strip()
        cleaned = cleaned.lstrip("0123456789").lstrip(".").strip() if cleaned[:1].isdigit() else cleaned
        if cleaned:
            claims.append(cleaned)
    return claims


def build_supported_check_prompt(claim: str, source_text: str) -> str:
    return (
        "Câu khẳng định sau có được ĐOẠN TÀI LIỆU dưới đây xác nhận không? Chỉ trả lời đúng 1 từ "
        '"CÓ" hoặc "KHÔNG", không giải thích.\n\n'
        f"CÂU KHẲNG ĐỊNH: {claim}\n\n"
        f"ĐOẠN TÀI LIỆU:\n{source_text}"
    )


def build_relevance_check_prompt(chunk_text: str, task_objective: str) -> str:
    return (
        "Đoạn tài liệu dưới đây có LIÊN QUAN tới mục tiêu của task không (đủ để giúp hoàn thành "
        'task, không lạc đề)? Chỉ trả lời đúng 1 từ "CÓ" hoặc "KHÔNG", không giải thích.\n\n'
        f"MỤC TIÊU TASK: {task_objective}\n\n"
        f"ĐOẠN TÀI LIỆU:\n{chunk_text}"
    )


def parse_yes_no(response_text: str) -> bool:
    """True nếu model trả "CÓ" (chấp nhận có dấu câu/khoảng trắng thừa quanh, không phân biệt hoa
    thường) — bất cứ câu trả lời nào KHÁC (kể cả rỗng/lỗi) coi là "KHÔNG" (an toàn hơn: 1 claim
    không xác nhận được thì tính là KHÔNG được hỗ trợ, không tính nhầm thành CÓ)."""
    normalised = response_text.strip().upper()
    return normalised.startswith("CÓ") or normalised.startswith("CO")


def build_batch_supported_check_prompt(claims: list[str], source_text: str) -> str:
    """Gộp NHIỀU claim vào 1 lời gọi — giảm số request tới judge model (xem MAX_ITEMS_PER_JUDGE_BATCH
    vì sao cần gộp). Câu hỏi giữ nguyên ngữ nghĩa với bản 1-claim-1-lời-gọi, chỉ đổi định dạng trả
    lời thành danh sách có số thứ tự để tách lại được từng câu."""
    numbered = "\n".join(f"{i + 1}. {claim}" for i, claim in enumerate(claims))
    return (
        "Với MỖI câu khẳng định được đánh số dưới đây, cho biết ĐOẠN TÀI LIỆU có xác nhận được câu "
        'đó không. Trả lời đúng N dòng (N = số câu khẳng định), mỗi dòng theo định dạng '
        '"<số thứ tự>. CÓ" hoặc "<số thứ tự>. KHÔNG", không giải thích gì thêm.\n\n'
        f"CÁC CÂU KHẲNG ĐỊNH:\n{numbered}\n\n"
        f"ĐOẠN TÀI LIỆU:\n{source_text}"
    )


def build_batch_relevance_check_prompt(chunks: list[str], task_objective: str) -> str:
    """Biến thể gộp lô của `build_relevance_check_prompt` — dùng cho Context Precision khi 1 task
    có nhiều đoạn tài liệu (vd nhóm COMPANY đọc toàn bộ policy, có thể tới hàng chục đoạn)."""
    numbered = "\n\n".join(f"[{i + 1}]\n{chunk}" for i, chunk in enumerate(chunks))
    return (
        "Với MỖI đoạn tài liệu được đánh số dưới đây, đoạn đó có LIÊN QUAN tới mục tiêu task không "
        "(đủ để giúp hoàn thành task, không lạc đề)? Trả lời đúng N dòng (N = số đoạn), mỗi dòng "
        'theo định dạng "<số thứ tự>. CÓ" hoặc "<số thứ tự>. KHÔNG", không giải thích gì thêm.\n\n'
        f"MỤC TIÊU TASK: {task_objective}\n\n"
        f"CÁC ĐOẠN TÀI LIỆU:\n{numbered}"
    )


_BATCH_LINE_RE = re.compile(r"^\s*(\d+)[.\):]?\s*(.+?)\s*$")


def parse_batch_yes_no(response_text: str, count: int) -> list[bool]:
    """Đọc kết quả của 2 hàm build_batch_* trên — khớp theo SỐ THỨ TỰ ghi trong câu trả lời (không
    theo VỊ TRÍ dòng, vì model đôi khi bỏ dòng trống hoặc gộp 2 ý 1 dòng). Số nào thiếu trong câu trả
    lời thì mặc định KHÔNG (an toàn hơn — không đọc được thì coi là chưa xác nhận, giống
    `parse_yes_no`)."""
    results = [False] * count
    for line in response_text.splitlines():
        match = _BATCH_LINE_RE.match(line)
        if not match:
            continue
        index = int(match.group(1)) - 1
        if 0 <= index < count:
            results[index] = parse_yes_no(match.group(2))
    return results


def build_judge_prompt_with_reference(reference_content: str, ai_content: str) -> str:
    return (
        "Bạn là chuyên gia đánh giá nội dung onboarding kỹ sư. So sánh 2 bản dưới đây.\n\n"
        f"BẢN CHUẨN (do PM viết): {reference_content}\n\n"
        f"BẢN AI SINH: {ai_content}\n\n"
        "Chấm điểm 1-5 cho từng tiêu chí, PHẢI giải thích ngắn TRƯỚC khi cho điểm (chain-of-thought):\n"
        "1. correctness — thông tin đúng, không bịa\n"
        "2. relevance — đúng phạm vi task, không lạc đề\n"
        "3. completeness — đủ chi tiết PM cần\n"
        "4. coherence — dễ đọc, có cấu trúc\n\n"
        'Trả JSON đúng định dạng: {"correctness": {"reasoning": "...", "score": N}, '
        '"relevance": {"reasoning": "...", "score": N}, "completeness": {"reasoning": "...", '
        '"score": N}, "coherence": {"reasoning": "...", "score": N}}'
    )


def build_judge_prompt_no_reference(ai_content: str, task_objective: str) -> str:
    """Biến thể KHÔNG có bản chuẩn tham chiếu — dùng cho case chưa có `reference_content` (xem
    plan-evaluation.md mục 4 vì sao không phải mọi case đều có bản chuẩn PM/assistant viết tay).
    Chấm tuyệt đối theo mục tiêu task, không so sánh."""
    return (
        "Bạn là chuyên gia đánh giá nội dung onboarding kỹ sư. Chấm bản nội dung AI sinh dưới đây "
        "theo đúng mục tiêu task (không có bản chuẩn để so sánh, chấm tuyệt đối).\n\n"
        f"MỤC TIÊU TASK: {task_objective}\n\n"
        f"BẢN AI SINH: {ai_content}\n\n"
        "Chấm điểm 1-5 cho từng tiêu chí, PHẢI giải thích ngắn TRƯỚC khi cho điểm (chain-of-thought):\n"
        "1. correctness — thông tin đúng, không bịa\n"
        "2. relevance — đúng phạm vi task, không lạc đề\n"
        "3. completeness — đủ chi tiết để làm được task\n"
        "4. coherence — dễ đọc, có cấu trúc\n\n"
        'Trả JSON đúng định dạng: {"correctness": {"reasoning": "...", "score": N}, '
        '"relevance": {"reasoning": "...", "score": N}, "completeness": {"reasoning": "...", '
        '"score": N}, "coherence": {"reasoning": "...", "score": N}}'
    )


def parse_judge_response(response_text: str) -> dict[str, dict] | None:
    """Bóc JSON khỏi câu trả lời judge, chịu được ```json bọc thừa (cùng kiểu xử lý với
    `content_llm._extract_json_array`). Trả `None` nếu không parse được hoặc thiếu tiêu chí —
    người gọi tự quyết định retry/bỏ qua case đó, không ném exception ở tầng parser thuần."""
    cleaned = response_text.strip()
    left = cleaned.find("{")
    right = cleaned.rfind("}")
    if left == -1 or right <= left:
        return None
    try:
        parsed = json.loads(cleaned[left : right + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict):
        return None
    for criterion in JUDGE_CRITERIA:
        entry = parsed.get(criterion)
        if not isinstance(entry, dict) or "score" not in entry:
            return None
        try:
            score = int(entry["score"])
        except (TypeError, ValueError):
            return None
        if not (1 <= score <= 5):
            return None
    return parsed


def judge_mean_score(parsed_judge: dict[str, dict]) -> float:
    """Điểm trung bình 4 tiêu chí — 1 số duy nhất để so nhanh AI vs Baseline, KHÔNG thay thế bảng
    chi tiết theo từng tiêu chí trong report (mục 10 của plan)."""
    scores = [int(parsed_judge[c]["score"]) for c in JUDGE_CRITERIA]
    return sum(scores) / len(scores)
