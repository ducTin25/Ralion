"""Xác minh 1 câu trích dẫn có THẬT nằm trong văn bản nguồn hay không.

Đặt trong `plan_generation` (không phải `src/ai/`) vì đây là code của module PM: luồng chat và
embeddings do thành viên khác sở hữu, không sửa sang bên đó.

Luật ở đây CỐ Ý trùng với `src/ai/orchestration/answer_generator._verified_substring` của luồng
chat — cùng một định nghĩa "trích dẫn hợp lệ" cho cả 2 luồng. Không import chéo sang file đó để
khỏi tạo phụ thuộc vào module người khác đang sửa; thay vào đó `test_text_verification.py` có 1
test đối chiếu ngẫu nhiên 2 bản, hỏng ngay khi 2 bên bắt đầu lệch nhau (bắt được drift mà không
cần đụng vào code của họ).

Quy tắc: chỉ khoan dung với KHOẢNG TRẮNG và HOA/THƯỜNG. Không khoan dung với việc LLM diễn giải
lại, thêm/bớt chữ — mục đích của hàm này là chứng minh câu chữ có thật trong tài liệu, không phải
đo độ giống nhau.
"""

from __future__ import annotations

import re

_WHITESPACE = re.compile(r"\s+")


def normalise(value: str) -> str:
    """Gộp mọi khoảng trắng thành 1 dấu cách, bỏ đầu/cuối, hạ hoa-thường."""
    return _WHITESPACE.sub(" ", value).strip().casefold()


def verified_substring(quote: str, content: str) -> str | None:
    """Trả về đoạn trích NGUYÊN VĂN lấy từ `content` (bản do server sở hữu), hoặc `None` nếu không
    tìm thấy.

    Cố ý trả bản cắt từ `content` chứ không trả lại `quote` của LLM: kể cả khi khớp, thứ được lưu
    xuống DB/hiển thị cho người đọc phải là chữ của tài liệu, không phải chữ LLM gõ lại.

    Cách so: cắt cả 2 bên thành danh sách từ rồi trượt cửa sổ đúng bằng số từ của `quote`. Bản bên
    chat thử mọi cặp (start, end) — O(n²) lần ghép chuỗi, chấp nhận được khi mỗi câu trả lời chỉ
    kiểm vài trích dẫn, nhưng ở đây mỗi lượt sinh plan kiểm hàng trăm đoạn nên phải nhanh hơn. Hai
    cách cho KẾT QUẢ GIỐNG HỆT nhau vì `normalise` chỉ chuẩn hoá khoảng trắng và hoa-thường, nên
    chuỗi nối các từ đã chuẩn hoá bằng đúng chuẩn hoá của chuỗi nối (test đối chiếu chứng minh).
    """
    normalised_quote = normalise(quote)
    if not normalised_quote:
        return None

    words = re.findall(r"\S+", content)
    if not words:
        return None

    quote_words = normalised_quote.split(" ")
    span = len(quote_words)
    if span > len(words):
        return None

    lowered = [word.casefold() for word in words]
    first = quote_words[0]
    for start in range(len(words) - span + 1):
        if lowered[start] != first:
            continue
        if lowered[start : start + span] == quote_words:
            return " ".join(words[start : start + span])
    return None
