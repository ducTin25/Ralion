"""Thống kê thuần (mean/std, % thắng, % lệch calibrate) cho scripts/eval_plan_content.py.

Tách riêng khỏi phần gọi LLM để test bằng pytest thường — xem plan-evaluation.md mục 7 (statistical
rigor) và mục 8 (calibrate).
"""

from __future__ import annotations

import statistics


def mean_std(values: list[float]) -> tuple[float, float]:
    """`std = 0.0` khi chỉ có 1 giá trị (population trần 1 phần tử không có phương sai) — KHÔNG ném
    lỗi như `statistics.stdev` (đòi hỏi >= 2 phần tử), vì baseline B0 deterministic chỉ chạy 1 lần
    (xem mục 6) nên hàm này phải xử lý được cả trường hợp N=1."""
    if not values:
        raise ValueError("mean_std: values rỗng")
    mean = statistics.fmean(values)
    std = statistics.pstdev(values) if len(values) > 1 else 0.0
    return mean, std


def win_rate(ai_scores: list[float], baseline_scores: list[float]) -> float:
    """% case AI có điểm trung bình (qua các lần chạy) CAO HƠN baseline — mục 6. Yêu cầu 2 danh
    sách cùng độ dài, phần tử thứ i của mỗi danh sách ứng với cùng 1 case."""
    if len(ai_scores) != len(baseline_scores):
        raise ValueError("win_rate: 2 danh sách phải cùng độ dài (cùng chỉ số case)")
    if not ai_scores:
        return 0.0
    wins = sum(1 for ai, base in zip(ai_scores, baseline_scores, strict=True) if ai > base)
    return wins / len(ai_scores)


def calibration_agreement_rate(human_scores: list[float], judge_scores: list[float], tolerance: float = 1.0) -> float:
    """% case có |điểm người - điểm judge| <= tolerance — proxy cho Cohen's kappa (mục 8, ghi rõ
    đây là compromise vì quy mô đồ án không đủ 2 chuyên gia độc lập)."""
    if len(human_scores) != len(judge_scores):
        raise ValueError("calibration_agreement_rate: 2 danh sách phải cùng độ dài")
    if not human_scores:
        return 0.0
    agree = sum(
        1 for h, j in zip(human_scores, judge_scores, strict=True) if abs(h - j) <= tolerance
    )
    return agree / len(human_scores)
