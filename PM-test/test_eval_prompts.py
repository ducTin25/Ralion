"""Test phần THUẦN (không gọi LLM) của scripts/eval_plan_content.py: build prompt + parse response.

Đây là phần duy nhất của eval script test được bằng pytest thường không cần key/API thật (phần gọi
Groq thật được verify riêng bằng chạy `--pilot` — xem docs/PM/report-evaluation.md)."""

import pytest

from scripts import eval_prompts


class TestParseClaimsResponse:
    def test_splits_by_line(self):
        text = "Claim một.\nClaim hai.\nClaim ba."
        assert eval_prompts.parse_claims_response(text) == ["Claim một.", "Claim hai.", "Claim ba."]

    def test_strips_numbering_and_bullets(self):
        text = "1. Claim một\n- Claim hai\n* Claim ba\n• Claim bốn"
        assert eval_prompts.parse_claims_response(text) == [
            "Claim một",
            "Claim hai",
            "Claim ba",
            "Claim bốn",
        ]

    def test_drops_empty_lines(self):
        text = "Claim một\n\n\nClaim hai\n   \n"
        assert eval_prompts.parse_claims_response(text) == ["Claim một", "Claim hai"]

    def test_empty_input_returns_empty_list(self):
        assert eval_prompts.parse_claims_response("") == []


class TestParseYesNo:
    @pytest.mark.parametrize("text", ["CÓ", "Có", "có", "  CÓ.", "CÓ, vì tài liệu nói vậy"])
    def test_accepts_yes_variants(self, text):
        assert eval_prompts.parse_yes_no(text) is True

    @pytest.mark.parametrize("text", ["KHÔNG", "Không", "  không.", "", "N/A", "CO KHONG"])
    def test_rejects_everything_else_as_no(self, text):
        # "CO KHONG" bắt đầu bằng "CO" (không dấu) nên vẫn được coi là CÓ theo luật khoan dung
        # dấu — trừ đúng case đó, còn lại phải là KHÔNG.
        if text == "CO KHONG":
            assert eval_prompts.parse_yes_no(text) is True
        else:
            assert eval_prompts.parse_yes_no(text) is False

    def test_ascii_no_diacritics_variant_accepted(self):
        assert eval_prompts.parse_yes_no("CO") is True


class TestParseJudgeResponse:
    VALID = (
        '{"correctness": {"reasoning": "r1", "score": 4}, '
        '"relevance": {"reasoning": "r2", "score": 5}, '
        '"completeness": {"reasoning": "r3", "score": 3}, '
        '"coherence": {"reasoning": "r4", "score": 4}}'
    )

    def test_parses_valid_json(self):
        parsed = eval_prompts.parse_judge_response(self.VALID)
        assert parsed is not None
        assert parsed["correctness"]["score"] == 4

    def test_tolerates_markdown_fence_wrapper(self):
        wrapped = f"Đây là kết quả:\n```json\n{self.VALID}\n```\nHết."
        parsed = eval_prompts.parse_judge_response(wrapped)
        assert parsed is not None
        assert parsed["relevance"]["score"] == 5

    def test_missing_criterion_returns_none(self):
        broken = (
            '{"correctness": {"reasoning": "r1", "score": 4}, '
            '"relevance": {"reasoning": "r2", "score": 5}, '
            '"completeness": {"reasoning": "r3", "score": 3}}'
        )
        assert eval_prompts.parse_judge_response(broken) is None

    def test_score_out_of_range_returns_none(self):
        broken = self.VALID.replace('"score": 4', '"score": 9', 1)
        assert eval_prompts.parse_judge_response(broken) is None

    def test_non_numeric_score_returns_none(self):
        broken = self.VALID.replace('"score": 4', '"score": "cao"', 1)
        assert eval_prompts.parse_judge_response(broken) is None

    def test_garbage_text_returns_none(self):
        assert eval_prompts.parse_judge_response("Xin lỗi, tôi không thể chấm điểm.") is None

    def test_empty_string_returns_none(self):
        assert eval_prompts.parse_judge_response("") is None


class TestJudgeMeanScore:
    def test_averages_four_criteria(self):
        parsed = eval_prompts.parse_judge_response(TestParseJudgeResponse.VALID)
        # (4 + 5 + 3 + 4) / 4 = 4.0
        assert eval_prompts.judge_mean_score(parsed) == 4.0

    def test_all_same_score(self):
        parsed = {c: {"score": 3} for c in eval_prompts.JUDGE_CRITERIA}
        assert eval_prompts.judge_mean_score(parsed) == 3.0


class TestParseBatchYesNo:
    def test_matches_by_number_not_position(self):
        text = "1. CÓ\n2. KHÔNG\n3. CÓ"
        assert eval_prompts.parse_batch_yes_no(text, 3) == [True, False, True]

    def test_tolerates_reordered_lines(self):
        text = "3. CÓ\n1. KHÔNG\n2. CÓ"
        assert eval_prompts.parse_batch_yes_no(text, 3) == [False, True, True]

    def test_missing_number_defaults_to_false(self):
        text = "1. CÓ\n3. CÓ"  # thiếu số 2
        assert eval_prompts.parse_batch_yes_no(text, 3) == [True, False, True]

    def test_tolerates_bracket_and_paren_numbering(self):
        text = "1) CÓ\n2: KHÔNG"
        assert eval_prompts.parse_batch_yes_no(text, 2) == [True, False]

    def test_ignores_out_of_range_numbers(self):
        text = "1. CÓ\n99. CÓ"
        assert eval_prompts.parse_batch_yes_no(text, 1) == [True]

    def test_empty_response_all_false(self):
        assert eval_prompts.parse_batch_yes_no("", 3) == [False, False, False]

    def test_garbage_lines_ignored(self):
        text = "Đây là kết quả:\n1. CÓ\n(giải thích thêm không liên quan)\n2. KHÔNG"
        assert eval_prompts.parse_batch_yes_no(text, 2) == [True, False]


class TestBatchPromptBuilders:
    def test_supported_check_numbers_every_claim(self):
        prompt = eval_prompts.build_batch_supported_check_prompt(["claim A", "claim B"], "nguồn X")
        assert "1. claim A" in prompt
        assert "2. claim B" in prompt
        assert "nguồn X" in prompt

    def test_relevance_check_numbers_every_chunk(self):
        prompt = eval_prompts.build_batch_relevance_check_prompt(["chunk A", "chunk B"], "mục tiêu Y")
        assert "[1]" in prompt and "chunk A" in prompt
        assert "[2]" in prompt and "chunk B" in prompt
        assert "mục tiêu Y" in prompt


class TestPromptBuildersContainRequiredContent:
    """Sanity: prompt phải nhắc đúng nội dung cần — không kiểm tra wording cứng nhắc để không vỡ
    test mỗi lần chỉnh câu chữ, chỉ kiểm tra các phần TỬ bắt buộc phải có mặt."""

    def test_judge_with_reference_includes_both_texts(self):
        prompt = eval_prompts.build_judge_prompt_with_reference("BẢN CHUẨN X", "BẢN AI Y")
        assert "BẢN CHUẨN X" in prompt
        assert "BẢN AI Y" in prompt
        for criterion in eval_prompts.JUDGE_CRITERIA:
            assert criterion in prompt

    def test_judge_no_reference_includes_objective_and_content(self):
        prompt = eval_prompts.build_judge_prompt_no_reference("BẢN AI Y", "MỤC TIÊU Z")
        assert "BẢN AI Y" in prompt
        assert "MỤC TIÊU Z" in prompt
        assert "reference" not in prompt.lower() or "BẢN CHUẨN" not in prompt

    def test_extract_claims_prompt_includes_text(self):
        assert "đoạn văn nguồn abc" in eval_prompts.build_extract_claims_prompt("đoạn văn nguồn abc")

    def test_supported_check_prompt_includes_claim_and_source(self):
        prompt = eval_prompts.build_supported_check_prompt("claim X", "source Y")
        assert "claim X" in prompt
        assert "source Y" in prompt

    def test_relevance_check_prompt_includes_chunk_and_objective(self):
        prompt = eval_prompts.build_relevance_check_prompt("chunk X", "objective Y")
        assert "chunk X" in prompt
        assert "objective Y" in prompt
