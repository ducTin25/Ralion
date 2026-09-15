"""Test phần THUẦN của scripts/eval_plan_content.py — cắt ngắn tài liệu gửi cho judge model
(Groq free tier trần 8000 token/phút, xem docs/PM/report-evaluation.md mục 7 cho bối cảnh thật)."""

from scripts.eval_plan_content import (
    MAX_CHUNK_CHARS_FOR_JUDGE,
    MAX_TOTAL_CHUNK_CHARS_FOR_JUDGE,
    _cap_chunks_for_judge,
)


class TestCapChunksForJudge:
    def test_short_chunks_pass_through_unchanged(self):
        chunks = ["chunk ngắn 1", "chunk ngắn 2"]
        assert _cap_chunks_for_judge(chunks) == chunks

    def test_each_chunk_truncated_to_max_chars(self):
        long_chunk = "x" * (MAX_CHUNK_CHARS_FOR_JUDGE + 500)
        result = _cap_chunks_for_judge([long_chunk])
        assert len(result[0]) == MAX_CHUNK_CHARS_FOR_JUDGE

    def test_stops_once_total_budget_reached(self):
        # Mỗi chunk chiếm đúng MAX_CHUNK_CHARS_FOR_JUDGE sau khi cắt -> số chunk tối đa lọt qua =
        # MAX_TOTAL_CHUNK_CHARS_FOR_JUDGE // MAX_CHUNK_CHARS_FOR_JUDGE
        chunk = "y" * MAX_CHUNK_CHARS_FOR_JUDGE
        many_chunks = [chunk] * 100
        result = _cap_chunks_for_judge(many_chunks)
        max_expected = MAX_TOTAL_CHUNK_CHARS_FOR_JUDGE // MAX_CHUNK_CHARS_FOR_JUDGE
        assert len(result) == max_expected

    def test_empty_input_returns_empty(self):
        assert _cap_chunks_for_judge([]) == []

    def test_never_exceeds_total_budget(self):
        chunks = ["z" * 300] * 50
        result = _cap_chunks_for_judge(chunks)
        assert sum(len(c) for c in result) <= MAX_TOTAL_CHUNK_CHARS_FOR_JUDGE
