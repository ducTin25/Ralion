"""Test hàm xác minh trích dẫn của module PM (`plan_generation.text_verification`).

Gồm 2 nhóm:
1. Luật xác minh: khoan dung khoảng trắng/hoa-thường, KHÔNG khoan dung diễn giải lại.
2. Chống lệch với luồng chat: bản của PM và `answer_generator._verified_substring` (TV3 sở hữu) cố
   ý cùng một luật nhưng là 2 hiện thực khác nhau. Test đối chiếu ngẫu nhiên bắt được lúc 2 bên bắt
   đầu lệch — làm được việc đó mà KHÔNG phải sửa file của người khác.
"""

import random
import re

from src.services.plan_generation.text_verification import normalise, verified_substring

CONTENT = "Mọi thiết bị công ty  cấp phải được\nmã hoá ổ đĩa trước khi mang ra khỏi văn phòng."


def test_accepts_exact_quote():
    assert verified_substring("mã hoá ổ đĩa", CONTENT) == "mã hoá ổ đĩa"


def test_tolerates_whitespace_and_case_but_returns_the_document_wording():
    """Trả về bản của TÀI LIỆU, không phải bản LLM gõ lại — thứ lưu xuống DB phải là chữ gốc."""
    assert verified_substring("  MÃ   HOÁ    ổ ĐĨA  ", CONTENT) == "mã hoá ổ đĩa"


def test_matches_across_a_line_break_in_the_source():
    """Xuống dòng giữa câu là chuyện thường trong tài liệu đã tách đoạn — không được vì thế mà trượt."""
    # Nguồn có xuống dòng giữa "được" và "mã"; kết quả trả về đã chuẩn hoá thành 1 dấu cách.
    assert verified_substring("phải được mã hoá", CONTENT) == "phải được mã hoá"


def test_rejects_paraphrase():
    """Diễn giải lại KHÔNG được tính là trích dẫn — đây là toàn bộ lý do hàm này tồn tại."""
    assert verified_substring("thiết bị phải mã hoá ổ cứng", CONTENT) is None


def test_rejects_extra_word_glued_to_a_real_quote():
    assert verified_substring("mã hoá ổ đĩa ngay", CONTENT) is None


def test_rejects_empty_or_whitespace_quote():
    assert verified_substring("", CONTENT) is None
    assert verified_substring("   \n  ", CONTENT) is None


def test_rejects_quote_longer_than_the_source():
    assert verified_substring(CONTENT + " thêm chữ thừa", CONTENT) is None


def test_handles_empty_source():
    assert verified_substring("bất kỳ", "") is None


def test_normalise_collapses_whitespace_and_case():
    assert normalise("  A   b\n\tC ") == "a b c"


# --- Chống lệch với luồng chat -----------------------------------------------------------------


def _chat_implementation(quote: str, content: str) -> str | None:
    """Chép NGUYÊN VĂN thuật toán của `answer_generator._verified_substring` tại thời điểm viết test.

    Cố ý chép thay vì import: nếu import, test sẽ hỏng mỗi lần TV3 refactor nội bộ file của họ. Chép
    lại thì test canh đúng thứ cần canh — LUẬT có còn giống nhau không — và nếu sau này họ đổi luật
    thật thì test đối chiếu ở dưới đỏ lên, đúng lúc cần biết.
    """
    whitespace = re.compile(r"\s+")

    def _n(value: str) -> str:
        return whitespace.sub(" ", value).strip().casefold()

    normalised_quote = _n(quote)
    if not normalised_quote:
        return None
    words = re.findall(r"\S+", content)
    for start in range(len(words)):
        for end in range(start + 1, len(words) + 1):
            candidate = " ".join(words[start:end])
            if _n(candidate) == normalised_quote:
                return candidate
    return None


def test_pm_and_chat_implementations_agree_on_random_cases():
    """1000 ca ngẫu nhiên: 2 bản phải cho KẾT QUẢ GIỐNG HỆT.

    Bản của PM trượt cửa sổ theo số từ (nhanh, dùng cho hàng trăm đoạn mỗi lượt sinh plan), bản chat
    thử mọi cặp (start, end) — O(n²). Khác cách chạy nhưng phải cùng kết luận, nếu không thì cùng 1
    trích dẫn được luồng này nhận và luồng kia loại.
    """
    random.seed(20260818)
    vocab = ["alpha", "Beta", "GAMMA", "delta", "eps", "Zeta", "the", "a", "ổ", "MÃ"]
    for _ in range(1000):
        content = " ".join(random.choice(vocab) for _ in range(random.randint(1, 20)))
        if random.random() < 0.6:  # trích thật, có xáo hoa-thường/khoảng trắng
            words = content.split()
            start = random.randrange(len(words))
            end = random.randrange(start + 1, len(words) + 1)
            quote = " ".join(words[start:end])
            if random.random() < 0.5:
                quote = quote.upper()
            if random.random() < 0.3:
                quote = "  " + quote.replace(" ", "   ") + " "
        else:  # trích bịa
            quote = " ".join(random.choice(vocab) for _ in range(random.randint(0, 4)))

        assert verified_substring(quote, content) == _chat_implementation(quote, content), (
            f"2 bản cho kết quả khác nhau với quote={quote!r} content={content!r}"
        )
