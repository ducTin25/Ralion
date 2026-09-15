import type { ReactNode } from "react";

/** Biến text heading thành id ổn định để cuộn tới đúng mục khi mở trích dẫn.
 * Bỏ dấu tiếng Việt trước khi slug hoá, nếu không "Cài đặt môi trường" và "Cai dat moi truong"
 * (cùng 1 mục, khác cách gõ) sẽ ra 2 id khác nhau và không khớp được. */
export function slugifyHeading(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/đ/g, "d")
    .replace(/Đ/g, "D")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}

export type MarkdownHeading = {
  id: string;
  text: string;
  level: 1 | 2 | 3;
  index: number;
};

/**
 * Trích xuất heading bằng đúng quy tắc mà renderer dùng. ID được khử trùng lặp theo thứ tự xuất
 * hiện để mục lục và nội dung luôn trỏ tới cùng một phần, kể cả khi AI lặp lại tên nhóm.
 */
function extractMarkdownHeadings(source: string): MarkdownHeading[] {
  const occurrences = new Map<string, number>();
  const headings: MarkdownHeading[] = [];

  for (const rawLine of source.replace(/\r\n/g, "\n").split("\n")) {
    const line = rawLine.trimEnd();
    const match = /^(#{1,3})\s+(.+)$/.exec(line);
    if (!match) continue;

    const level = match[1].length as 1 | 2 | 3;
    const text = match[2].trim();
    const baseId = slugifyHeading(text) || "section";
    const occurrence = (occurrences.get(baseId) ?? 0) + 1;
    occurrences.set(baseId, occurrence);
    headings.push({
      id: occurrence === 1 ? baseId : `${baseId}-${occurrence}`,
      text,
      level,
      index: headings.length,
    });
  }

  return headings;
}

/** Outline dành cho reading workspace: tiêu đề cấp 2 là section, cấp 3 là nhóm con. */
export function extractMarkdownOutline(source: string): MarkdownHeading[] {
  return extractMarkdownHeadings(source).filter((heading) => heading.level >= 2);
}

type InlineOptions = {
  /** Số nguồn hợp lệ — `[n]` vượt quá thì render như text thường, không thành nút bấm chết. */
  citationCount?: number;
  onCitationClick?: (index: number) => void;
};

/** Render inline markdown (bold/code/link/trích dẫn `[n]`) trong 1 dòng text thành mảng ReactNode —
 * không dùng `dangerouslySetInnerHTML` (tránh XSS từ nội dung tài liệu tải về), tự tách token bằng
 * regex. */
function renderInline(text: string, options: InlineOptions = {}): ReactNode[] {
  const { citationCount = 0, onCitationClick } = options;
  const tokenPattern = /(\*\*[^*]+\*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|\[\d+\])/g;
  const parts = text.split(tokenPattern).filter((part) => part !== "");

  return parts.map((part, i) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={i}>{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={i}>{part.slice(1, -1)}</code>;
    }
    const linkMatch = /^\[([^\]]+)\]\(([^)]+)\)$/.exec(part);
    if (linkMatch) {
      return (
        <a key={i} href={linkMatch[2]} target="_blank" rel="noopener noreferrer">
          {linkMatch[1]}
        </a>
      );
    }
    // Trích dẫn `[n]` do AI chèn ngay tại bước dùng nguồn đó (xem prompts.py quy tắc 5). Bấm vào mở
    // đúng đoạn tài liệu thay vì bắt người đọc dò trong danh sách nguồn ở cuối trang.
    const citationMatch = /^\[(\d+)\]$/.exec(part);
    if (citationMatch) {
      const index = Number(citationMatch[1]);
      if (index >= 1 && index <= citationCount && onCitationClick) {
        return (
          <button
            key={i}
            type="button"
            className="pm-citation"
            title={`View source ${index}`}
            onClick={() => onCitationClick(index)}
          >
            {index}
          </button>
        );
      }
      return <span key={i}>{part}</span>;
    }
    return part;
  });
}

type MarkdownOptions = InlineOptions & {
  /** Trả về phần tử chèn TRƯỚC nội dung tiêu đề (vd icon nhóm chính sách), hoặc null nếu không có.
   * Tuỳ chọn: nơi gọi không truyền thì heading render y như cũ — Member Portal đang dùng hàm này
   * không bị ảnh hưởng gì. */
  headingPrefix?: (text: string, level: 1 | 2 | 3) => ReactNode | null;
};

/** Render markdown đơn giản (heading #/##/###, danh sách `- `/`1. `, checkbox `- [ ]`, đoạn văn,
 * inline bold/code/link/trích dẫn) thành JSX — đủ dùng cho tài liệu dự án + nội dung task AI sinh
 * (không cần thêm thư viện markdown ngoài). */
export function renderMarkdown(source: string, options: MarkdownOptions = {}): ReactNode {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const headings = extractMarkdownHeadings(source);
  let headingIndex = 0;
  const blocks: ReactNode[] = [];
  let bulletBuffer: string[] = [];
  let orderedBuffer: string[] = [];
  let checkboxBuffer: { checked: boolean; text: string }[] = [];

  function flushBullets() {
    if (bulletBuffer.length === 0) return;
    blocks.push(
      <ul key={`ul-${blocks.length}`}>
        {bulletBuffer.map((item, i) => (
          <li key={i}>{renderInline(item, options)}</li>
        ))}
      </ul>,
    );
    bulletBuffer = [];
  }

  function flushOrdered() {
    if (orderedBuffer.length === 0) return;
    blocks.push(
      <ol key={`ol-${blocks.length}`}>
        {orderedBuffer.map((item, i) => (
          <li key={i}>{renderInline(item, options)}</li>
        ))}
      </ol>,
    );
    orderedBuffer = [];
  }

  function flushCheckboxes() {
    if (checkboxBuffer.length === 0) return;
    blocks.push(
      // `disabled`: đây là tiêu chí nghiệm thu để đọc, không phải checklist tương tác — PlanTask chỉ
      // lưu status của cả task, không lưu trạng thái từng dòng.
      <ul key={`cl-${blocks.length}`} className="pm-checklist">
        {checkboxBuffer.map((item, i) => (
          <li key={i}>
            <input type="checkbox" checked={item.checked} disabled readOnly />
            <span>{renderInline(item.text, options)}</span>
          </li>
        ))}
      </ul>,
    );
    checkboxBuffer = [];
  }

  let paragraphBuffer: string[] = [];
  function flushParagraph() {
    if (paragraphBuffer.length === 0) return;
    blocks.push(
      <p key={`p-${blocks.length}`}>{renderInline(paragraphBuffer.join(" "), options)}</p>,
    );
    paragraphBuffer = [];
  }

  let quoteBuffer: string[] = [];
  function flushQuote() {
    if (quoteBuffer.length === 0) return;
    blocks.push(
      <blockquote key={`q-${blocks.length}`} className="pm-quote">
        {renderInline(quoteBuffer.join(" "), options)}
      </blockquote>,
    );
    quoteBuffer = [];
  }

  function flushAll() {
    flushParagraph();
    flushQuote();
    flushBullets();
    flushOrdered();
    flushCheckboxes();
  }

  function pushHeading(level: 1 | 2 | 3, text: string) {
    flushAll();
    const heading = headings[headingIndex];
    const id = heading?.id ?? slugifyHeading(text);
    headingIndex += 1;
    const prefix = options.headingPrefix?.(text, level) ?? null;
    const children = (
      <>
        {prefix}
        {renderInline(text, options)}
      </>
    );
    const key = `h-${blocks.length}`;
    if (level === 1)
      blocks.push(
        <h1 key={key} id={id}>
          {children}
        </h1>,
      );
    else if (level === 2)
      blocks.push(
        <h2 key={key} id={id}>
          {children}
        </h2>,
      );
    else
      blocks.push(
        <h3 key={key} id={id}>
          {children}
        </h3>,
      );
  }

  for (const rawLine of lines) {
    const line = rawLine.trimEnd();
    if (line.trim() === "") {
      flushAll();
      continue;
    }
    if (line.startsWith("### ")) {
      pushHeading(3, line.slice(4));
      continue;
    }
    if (line.startsWith("## ")) {
      pushHeading(2, line.slice(3));
      continue;
    }
    if (line.startsWith("# ")) {
      pushHeading(1, line.slice(2));
      continue;
    }

    // Trích dẫn khối "> ..." — dùng cho các câu nhắc quan trọng trong nội dung task (cảnh báo thiếu
    // tài liệu, câu dặn đọc hết bản gốc). Trước đây không có nhánh này nên chúng hiện nguyên ký tự
    // ">" giữa đoạn văn.
    const quoteMatch = /^>\s?(.*)$/.exec(line);
    if (quoteMatch) {
      flushParagraph();
      flushBullets();
      flushOrdered();
      flushCheckboxes();
      quoteBuffer.push(quoteMatch[1]);
      continue;
    }

    // Checkbox phải thử TRƯỚC bullet thường: cả hai đều mở đầu bằng "- ".
    const checkboxMatch = /^[-*]\s+\[([ xX])\]\s+(.*)$/.exec(line);
    if (checkboxMatch) {
      flushParagraph();
      flushQuote();
      flushBullets();
      flushOrdered();
      checkboxBuffer.push({
        checked: checkboxMatch[1].toLowerCase() === "x",
        text: checkboxMatch[2],
      });
      continue;
    }

    // Danh sách đánh số ("1. " / "2) ") — trước đây rơi vào nhánh đoạn văn nên các bước bị nối
    // thành 1 cục chữ liền, đúng lỗi PM thấy khi mở chi tiết task.
    const orderedMatch = /^\d+[.)]\s+(.*)$/.exec(line);
    if (orderedMatch) {
      flushParagraph();
      flushQuote();
      flushBullets();
      flushCheckboxes();
      orderedBuffer.push(orderedMatch[1]);
      continue;
    }

    if (line.startsWith("- ") || line.startsWith("* ")) {
      flushParagraph();
      flushQuote();
      flushOrdered();
      flushCheckboxes();
      bulletBuffer.push(line.slice(2));
      continue;
    }

    flushQuote();
    flushBullets();
    flushOrdered();
    flushCheckboxes();
    paragraphBuffer.push(line.trim());
  }
  flushAll();

  return blocks;
}
