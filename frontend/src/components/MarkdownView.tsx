import { Fragment, type ReactNode } from "react";

/**
 * Hiển thị Markdown dưới dạng văn bản có định dạng.
 *
 * Vì sao tự viết thay vì dùng `react-markdown`:
 *
 * 1. Không thêm dependency cho cả nhóm chỉ để render một tập cú pháp nhỏ.
 * 2. Renderer này dựng React element trực tiếp, KHÔNG dùng `dangerouslySetInnerHTML`.
 *    Nội dung ở đây đến từ file người dùng tải lên, nên đường nào cũng phải khử HTML;
 *    dựng element là cách khử triệt để nhất — không có chỗ cho thẻ script tồn tại.
 *
 * Tập cú pháp hỗ trợ (đủ cho tài liệu chính sách, không nhắm tới CommonMark đầy đủ):
 * heading `#`..`######`, danh sách `-`/`*` và `1.`, bảng `|`, trích dẫn `>`, đường kẻ
 * `---`, khối code ```, và inline `**đậm**`, `*nghiêng*`, `` `mã` ``, `[chữ](link)`.
 *
 * Cú pháp ngoài danh sách trên hiện nguyên văn thay vì biến mất — với tài liệu quy định
 * thì mất chữ nguy hiểm hơn là hiển thị hơi xấu.
 */

type Block =
  | { kind: "heading"; level: number; text: string }
  | { kind: "paragraph"; text: string }
  | { kind: "list"; ordered: boolean; items: string[] }
  | { kind: "quote"; text: string }
  | { kind: "code"; text: string }
  | { kind: "table"; header: string[]; rows: string[][] }
  | { kind: "rule" };

const HEADING = /^(#{1,6})\s+(.*)$/;
const BULLET = /^\s*[-*]\s+(.*)$/;
const ORDERED = /^\s*\d+[.)]\s+(.*)$/;
const QUOTE = /^>\s?(.*)$/;
const RULE = /^\s*([-*_])\1{2,}\s*$/;
const TABLE_ROW = /^\s*\|(.+)\|\s*$/;
const TABLE_DIVIDER = /^\s*\|[\s:|-]+\|\s*$/;

function splitRow(line: string): string[] {
  return line
    .replace(/^\s*\|/, "")
    .replace(/\|\s*$/, "")
    .split("|")
    .map((cell) => cell.trim());
}

export function parseMarkdown(source: string): Block[] {
  const lines = source.replace(/\r\n/g, "\n").split("\n");
  const blocks: Block[] = [];
  let paragraph: string[] = [];

  const flushParagraph = () => {
    if (paragraph.length > 0) {
      blocks.push({ kind: "paragraph", text: paragraph.join(" ") });
      paragraph = [];
    }
  };

  for (let index = 0; index < lines.length; index += 1) {
    const line = lines[index];

    if (line.trim().startsWith("```")) {
      flushParagraph();
      const buffer: string[] = [];
      index += 1;
      while (index < lines.length && !lines[index].trim().startsWith("```")) {
        buffer.push(lines[index]);
        index += 1;
      }
      blocks.push({ kind: "code", text: buffer.join("\n") });
      continue;
    }

    if (line.trim() === "") {
      flushParagraph();
      continue;
    }

    if (RULE.test(line)) {
      flushParagraph();
      blocks.push({ kind: "rule" });
      continue;
    }

    const heading = HEADING.exec(line);
    if (heading) {
      flushParagraph();
      blocks.push({ kind: "heading", level: heading[1].length, text: heading[2].trim() });
      continue;
    }

    // Bảng: dòng đầu là header, dòng kế là gạch phân cách, còn lại là dữ liệu.
    if (TABLE_ROW.test(line) && index + 1 < lines.length && TABLE_DIVIDER.test(lines[index + 1])) {
      flushParagraph();
      const header = splitRow(line);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && TABLE_ROW.test(lines[index])) {
        rows.push(splitRow(lines[index]));
        index += 1;
      }
      index -= 1;
      blocks.push({ kind: "table", header, rows });
      continue;
    }

    const quote = QUOTE.exec(line);
    if (quote) {
      flushParagraph();
      blocks.push({ kind: "quote", text: quote[1] });
      continue;
    }

    const bullet = BULLET.exec(line);
    const ordered = ORDERED.exec(line);
    if (bullet || ordered) {
      flushParagraph();
      const isOrdered = Boolean(ordered);
      const items: string[] = [(bullet ?? ordered)![1]];
      while (index + 1 < lines.length) {
        const next = lines[index + 1];
        const nextMatch = isOrdered ? ORDERED.exec(next) : BULLET.exec(next);
        if (!nextMatch) break;
        items.push(nextMatch[1]);
        index += 1;
      }
      blocks.push({ kind: "list", ordered: isOrdered, items });
      continue;
    }

    paragraph.push(line.trim());
  }

  flushParagraph();
  return blocks;
}

/** Xử lý `**đậm**`, `*nghiêng*`, `` `mã` `` và `[chữ](link)` trong một dòng. */
function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const pattern = /(\*\*[^*]+\*\*|\*[^*]+\*|`[^`]+`|\[[^\]]+\]\([^)]+\))/g;
  const nodes: ReactNode[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let counter = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) nodes.push(text.slice(lastIndex, match.index));
    const token = match[0];
    const key = `${keyPrefix}-${counter}`;
    counter += 1;

    if (token.startsWith("**")) {
      nodes.push(
        <strong key={key} className="font-bold text-navy">
          {token.slice(2, -2)}
        </strong>,
      );
    } else if (token.startsWith("`")) {
      nodes.push(
        <code key={key} className="rounded bg-[#f0f2f8] px-1.5 py-0.5 font-mono text-[13px]">
          {token.slice(1, -1)}
        </code>,
      );
    } else if (token.startsWith("[")) {
      const parsed = /\[([^\]]+)\]\(([^)]+)\)/.exec(token);
      const href = parsed?.[2] ?? "";
      // Chỉ cho phép http/https/mailto — chặn `javascript:` chèn qua file tải lên.
      const safe = /^(https?:|mailto:)/i.test(href);
      nodes.push(
        safe ? (
          <a
            key={key}
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-link underline"
          >
            {parsed?.[1]}
          </a>
        ) : (
          <span key={key}>{parsed?.[1]}</span>
        ),
      );
    } else {
      nodes.push(
        <em key={key} className="italic">
          {token.slice(1, -1)}
        </em>,
      );
    }
    lastIndex = match.index + token.length;
  }

  if (lastIndex < text.length) nodes.push(text.slice(lastIndex));
  return nodes;
}

const headingClass: Record<number, string> = {
  1: "mt-8 mb-3 text-2xl font-bold tracking-[-.02em] text-navy first:mt-0",
  2: "mt-7 mb-3 border-b border-divider pb-2 text-xl font-bold text-navy first:mt-0",
  3: "mt-6 mb-2 text-lg font-bold text-navy first:mt-0",
  4: "mt-5 mb-2 text-base font-bold text-navy first:mt-0",
  5: "mt-4 mb-2 text-sm font-bold text-navy first:mt-0",
  6: "mt-4 mb-2 text-sm font-bold text-text-secondary first:mt-0",
};

export function MarkdownView({ source, className = "" }: { source: string; className?: string }) {
  const blocks = parseMarkdown(source);

  if (blocks.length === 0) {
    return <p className="text-sm text-text-subtle">This document has no text content yet.</p>;
  }

  return (
    <div className={`text-[15px] leading-7 text-text ${className}`}>
      {blocks.map((block, index) => {
        const key = `block-${index}`;
        switch (block.kind) {
          case "heading": {
            const Tag = `h${Math.min(block.level + 1, 6)}` as "h2";
            return (
              <Tag key={key} className={headingClass[block.level] ?? headingClass[6]}>
                {renderInline(block.text, key)}
              </Tag>
            );
          }
          case "list":
            return block.ordered ? (
              <ol key={key} className="my-3 list-decimal space-y-1.5 pl-6">
                {block.items.map((item, itemIndex) => (
                  <li key={`${key}-${itemIndex}`}>{renderInline(item, `${key}-${itemIndex}`)}</li>
                ))}
              </ol>
            ) : (
              <ul key={key} className="my-3 list-disc space-y-1.5 pl-6 marker:text-[#8b97bd]">
                {block.items.map((item, itemIndex) => (
                  <li key={`${key}-${itemIndex}`}>{renderInline(item, `${key}-${itemIndex}`)}</li>
                ))}
              </ul>
            );
          case "quote":
            return (
              <blockquote
                key={key}
                className="my-4 border-l-4 border-[#c9d0e6] bg-[#fafbfe] py-2 pl-4 text-text-secondary"
              >
                {renderInline(block.text, key)}
              </blockquote>
            );
          case "code":
            return (
              <pre
                key={key}
                className="my-4 overflow-auto rounded-lg bg-[#f7f8fc] p-4 font-mono text-[13px] leading-6"
              >
                {block.text}
              </pre>
            );
          case "table":
            return (
              <div key={key} className="my-4 overflow-x-auto">
                <table className="w-full border-collapse text-sm">
                  <thead>
                    <tr className="bg-[#fafbfe]">
                      {block.header.map((cell, cellIndex) => (
                        <th
                          key={`${key}-h-${cellIndex}`}
                          className="border border-border px-3 py-2 text-left font-bold text-navy"
                        >
                          {renderInline(cell, `${key}-h-${cellIndex}`)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {block.rows.map((row, rowIndex) => (
                      <tr key={`${key}-r-${rowIndex}`}>
                        {row.map((cell, cellIndex) => (
                          <td
                            key={`${key}-r-${rowIndex}-${cellIndex}`}
                            className="border border-border px-3 py-2 align-top"
                          >
                            {renderInline(cell, `${key}-r-${rowIndex}-${cellIndex}`)}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            );
          case "rule":
            return <hr key={key} className="my-6 border-divider" />;
          default:
            return (
              <p key={key} className="my-3">
                <Fragment>{renderInline(block.text, key)}</Fragment>
              </p>
            );
        }
      })}
    </div>
  );
}
