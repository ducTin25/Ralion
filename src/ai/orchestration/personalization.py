"""Static, enum-keyed style presets for F5 response personalization.

Presentation-layer only (PERSONALIZE_CHATBOT_SPEC.md §0.2/§3): presets are looked up by
`ResponseLength`/`ResponseTone` value only, never built from free-form input, so a
preference can never introduce arbitrary text into the prompt. `STANDARD`/`NEUTRAL` are
deliberately empty so the default preference produces byte-identical prompts to F5's
current behaviour (see the "default not regression" test in test_answer_generator.py).

`AnswerLanguage`/`LANGUAGE_INSTRUCTIONS` (F5 Semantic Turn Interpreter rev. 2 §7.1(b)): today
nothing in the answer prompt ever tells the model what language to answer in -- it works only
because the model mirrors the question's language, which is fragile on a reuse turn where the
evidence is in a different language than a short re-presentation instruction. `language` is
`None` by default so `build_style_instruction`'s output -- and therefore the generated prompt --
stays byte-identical to before this parameter existed; only `ChatService`'s Phase 2 dispatcher
(turn-local `presentation.language` override or the detected question language) ever passes a
concrete value, never built from interpreter free text (a closed enum only).

**`TONE_INSTRUCTIONS` is a behavioural contract, not a mood word (rewritten 2026-08-25).** The
first pass described each tone with adjectives ("kiên nhẫn", "gần gũi", "thoải mái"). Adjectives
are not separable: a model reading three adjective lists produces three answers that differ in
filler words and barely in structure, and nothing about them is observable, so no test and no
eval can tell whether the preference did anything at all. Each tone below instead fixes a value
on the SAME five axes, in the same order, so the three presets are diffable side by side and a
reviewer can see exactly what changes:

  1. Opening    -- how the first sentence behaves.
  2. Structure  -- prose vs. scannable, and when each applies.
  3. Terminology-- what happens to a term the evidence uses that a newcomer may not know.
  4. Register   -- address and formality.
  5. Closing    -- what, if anything, follows the last supported point.

Each preset then ends with the ONE boundary that its own axis settings invite -- deliberately
different per tone, never three copies of one sentence. The generic invariant ("a presentation
control may never change a factual conclusion, the citation requirement, or normative strength")
is NOT repeated here: it lives once, in `grounded_answer_prompt_v4._PRESENTATION_SECTION`, and
`test_v4_presentation_is_declared_presentation_only` pins that separation. What each preset adds
is the specific failure mode that tone makes likely, which a generic clause cannot operationalize:

  * GUIDE  -- scannability tempts dropping a condition/exception to keep a bullet short.
  * MENTOR -- "explain the why" tempts inventing a rationale the evidence never gave. This was a
    real defect in the first pass, whose text asked for "giải thích lý do đằng sau quy ước" with
    no evidence qualifier at all.
  * BUDDY  -- reassurance tempts asserting a social fact about the team. The first pass literally
    scripted one ("câu này ai mới vào cũng hỏi"), which is an uncited claim about the company.

`NEUTRAL` stays `""` on purpose and that is its contract, not a gap: the base prompt's own
register IS the neutral behaviour, and an empty preset is what makes the default preference
produce byte-identical prompts (the "default not regression" test). Giving NEUTRAL text would
silently change generation for every user who never opened the preferences panel.

Language: these presets stay Vietnamese, matching the majority of production turns and their
previous form. Rewriting them in English is a real option -- every other system message in the
stack is English -- but `turn_interpreter`'s own diacritic-stripping incident is direct evidence
that the language a prompt is WRITTEN in leaks into what the model produces, and that trade is
not worth making blind. Revisit only with a live before/after, never as a tidy-up.
"""

import enum

from src.model.enums import ResponseLength, ResponseTone


class AnswerLanguage(enum.StrEnum):
    VI = "vi"
    EN = "en"

LENGTH_INSTRUCTIONS: dict[ResponseLength, str] = {
    ResponseLength.CONCISE: (
        "Trả lời ngắn gọn, tối đa 3-4 câu hoặc bullet points súc tích. Không giải thích thừa."
    ),
    ResponseLength.STANDARD: "",
    ResponseLength.DETAILED: (
        "Trả lời đầy đủ, có ví dụ và giải thích nguyên nhân/context khi phù hợp."
    ),
}

TONE_INSTRUCTIONS: dict[ResponseTone, str] = {
    # See the module docstring: "" is NEUTRAL's contract (the base prompt's own register), not a
    # missing preset. Do not fill this in.
    ResponseTone.NEUTRAL: "",
    ResponseTone.GUIDE: (
        "Phong cách trả lời — GUIDE (câu trả lời để TRA CỨU):\n"
        "- Mở đầu: câu đầu tiên phải là câu trả lời trực tiếp. Không mở bài, không nhắc lại câu "
        "hỏi, không xã giao.\n"
        "- Cấu trúc: khi nội dung có nhiều mục hoặc có thứ tự, dùng bullet / bước đánh số / "
        "heading ngắn. Chỉ viết văn xuôi khi nội dung thực sự là một ý duy nhất.\n"
        "- Thuật ngữ: giữ nguyên thuật ngữ, tên gọi, tên lệnh và tên tài liệu đúng như trong "
        "nguồn. Không diễn giải lại thành từ thông dụng.\n"
        "- Xưng hô: ngôi thứ hai, trung tính, không cảm thán.\n"
        "- Kết: dừng ngay khi hết thông tin. Không thêm câu chốt, không mời hỏi thêm.\n"
        "- Ranh giới của riêng phong cách này: cấu trúc dễ quét không bao giờ được đánh đổi bằng "
        "việc bỏ bớt điều kiện, ngoại lệ, hạn chót, người phê duyệt hay bước bắt buộc. Nếu một "
        "mục quá dài thì tách thành nhiều mục, không cắt nội dung."
    ),
    ResponseTone.MENTOR: (
        "Phong cách trả lời — MENTOR (câu trả lời để HIỂU):\n"
        "- Mở đầu: một câu định vị vấn đề (nội dung này nói về cái gì, áp dụng trong trường hợp "
        "nào) rồi mới trả lời chi tiết.\n"
        "- Cấu trúc: văn xuôi có mạch, nối các ý bằng quan hệ điều kiện / nguyên nhân / trình tự "
        "thay vì liệt kê rời rạc. Chỉ dùng bullet cho quy trình có thứ tự thật sự.\n"
        "- Thuật ngữ: khi nguồn dùng một thuật ngữ hoặc từ viết tắt mà người mới có thể chưa "
        "biết, thêm một cụm giải nghĩa ngắn ngay tại chỗ — và CHỈ khi nghĩa đó có sẵn trong "
        "nguồn hoặc là cách diễn đạt lại của chính nguồn.\n"
        "- Xưng hô: như một senior engineer nói với đồng nghiệp mới. Giải thích, không dạy dỗ, "
        "không khen ngợi, không động viên.\n"
        "- Kết: nếu nguồn có nêu bước tiếp theo hoặc điều kiện tiên quyết, nêu nó ra như bước kế "
        "tiếp. Nếu nguồn không có, dừng lại.\n"
        "- Ranh giới của riêng phong cách này: chỉ trình bày lý do khi nguồn có nêu lý do đó. "
        "Tuyệt đối không tự suy ra vì sao một quy ước tồn tại, không tự gán mục đích hay động cơ "
        "cho một quy định. Nguồn không nói lý do thì trả lời quy định đó là gì và dừng — thiếu "
        "một lời giải thích là chấp nhận được, bịa ra một lời giải thích thì không."
    ),
    ResponseTone.BUDDY: (
        "Phong cách trả lời — BUDDY (câu trả lời để NGƯỜI HỎI ĐỠ NGẠI):\n"
        "- Mở đầu: đi thẳng vào câu trả lời. Nhiều nhất một mệnh đề ngắn trấn an đặt trước đó, "
        "và chỉ khi câu hỏi có dấu hiệu người hỏi đang ngại hoặc bối rối.\n"
        "- Cấu trúc: câu ngắn, văn xuôi đời thường. Dùng bullet khi có nhiều bước.\n"
        "- Thuật ngữ: giữ đúng tên gọi như trong nguồn, nhưng nói kèm bằng lời thường ngày ngay "
        "sau đó.\n"
        "- Xưng hô: thân mật (mình / bạn), không trang trọng, không dùng ngôn ngữ hành chính.\n"
        "- Kết: có thể kết bằng một lời mời hỏi tiếp, tối đa một câu.\n"
        "- Ranh giới của riêng phong cách này: lời trấn an chỉ được nói về việc HỎI (hỏi là bình "
        "thường, câu hỏi hợp lý). Không được khẳng định bất cứ điều gì về team, công ty hay "
        "người khác — 'ai mới vào cũng hỏi câu này', 'team mình thoải mái lắm', 'sếp bạn sẽ "
        "không phiền đâu' đều là claim không có nguồn. Giọng thoải mái cũng không được làm nhẹ "
        "đi một quy định bắt buộc, một hạn chót hay một yêu cầu phê duyệt: những chỗ đó vẫn phải "
        "nói dứt khoát."
    ),
}


# Emitted only when a length preset AND a tone preset are both non-empty, i.e. exactly when the
# two trusted style messages can pull in opposite directions ("Không giải thích thừa" from
# CONCISE vs. MENTOR's in-place gloss). Stating the precedence once here beats repeating a
# hedge inside every tone, and it is the only line in this module that is about how two presets
# COMPOSE rather than what one of them says.
_PRECEDENCE_NOTE = (
    "Khi hai chỉ dẫn trên xung đột: độ dài quyết định TRẢ LỜI BAO NHIÊU, phong cách quyết định "
    "TRẢ LỜI NHƯ THẾ NÀO. Cắt bớt phần mở rộng của phong cách trước, không bao giờ cắt một nội "
    "dung bắt buộc để vừa độ dài."
)


LANGUAGE_INSTRUCTIONS: dict[AnswerLanguage, str] = {
    AnswerLanguage.VI: "Trả lời bằng tiếng Việt.",
    AnswerLanguage.EN: "Answer in English.",
}


def build_style_instruction(
    response_length: ResponseLength,
    response_tone: ResponseTone,
    language: AnswerLanguage | None = None,
) -> str:
    """Look up static instruction text; never accepts free-form input.

    An unrecognized value (corrupted data predating the enum column) falls back to the
    empty baseline instead of raising — degrade to current F5 behaviour, don't break chat.

    `language=None` (the default) omits the language line entirely, so every existing caller
    that does not pass it keeps producing a byte-identical prompt.
    """
    length_part = LENGTH_INSTRUCTIONS.get(response_length, "")
    tone_part = TONE_INSTRUCTIONS.get(response_tone, "")
    language_part = LANGUAGE_INSTRUCTIONS.get(language, "") if language is not None else ""
    precedence_part = _PRECEDENCE_NOTE if (length_part and tone_part) else ""
    return "\n".join(
        part
        for part in (length_part, tone_part, precedence_part, language_part)
        if part
    )
