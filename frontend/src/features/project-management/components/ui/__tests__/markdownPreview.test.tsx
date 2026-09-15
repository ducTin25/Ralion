/**
 * Test cho `renderMarkdown` — tập trung vào tuỳ chọn `headingPrefix` mới thêm (gắn icon nhóm chính
 * sách vào tiêu đề `###` trong nội dung task do AI sinh).
 *
 * Điểm quan trọng nhất ở đây là ca "không truyền `headingPrefix`": Member Portal
 * (`member-onboarding/components/TaskDetailPage.tsx`, do thành viên khác sở hữu) gọi chung hàm này
 * và KHÔNG truyền tuỳ chọn mới. Test dưới chốt lại rằng nhánh đó render y như trước, để thay đổi
 * của module PM không lan sang màn hình của người khác.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { extractMarkdownOutline, renderMarkdown, slugifyHeading } from "../markdownPreview";

describe("renderMarkdown headingPrefix", () => {
  it("chèn phần tử trước nội dung tiêu đề khi có headingPrefix", () => {
    render(
      <div>
        {renderMarkdown("### Chính sách nhân sự\nNội dung", {
          headingPrefix: (text) => <span data-testid="icon">{`icon:${text}`}</span>,
        })}
      </div>,
    );

    const heading = screen.getByRole("heading", { level: 3 });
    expect(heading).toHaveTextContent("Chính sách nhân sự");
    expect(screen.getByTestId("icon")).toHaveTextContent("icon:Chính sách nhân sự");
  });

  it("giữ nguyên id của heading để trích dẫn cuộn tới đúng mục", () => {
    render(<div>{renderMarkdown("### Chính sách bảo mật", { headingPrefix: () => <i /> })}</div>);

    expect(screen.getByRole("heading", { level: 3 })).toHaveAttribute(
      "id",
      slugifyHeading("Chính sách bảo mật"),
    );
  });

  it("headingPrefix trả null thì không thêm gì", () => {
    const prefix = vi.fn().mockReturnValue(null);
    render(<div>{renderMarkdown("## Mục tiêu", { headingPrefix: prefix })}</div>);

    const heading = screen.getByRole("heading", { level: 2 });
    expect(heading.textContent).toBe("Mục tiêu");
    expect(prefix).toHaveBeenCalledWith("Mục tiêu", 2);
  });

  it("KHÔNG truyền headingPrefix thì render y như cũ (Member Portal không bị ảnh hưởng)", () => {
    const source = "## Mục tiêu\nDòng nội dung\n\n### Nhóm con\n- gạch đầu dòng";
    render(<div data-testid="plain">{renderMarkdown(source)}</div>);

    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("Mục tiêu");
    expect(screen.getByRole("heading", { level: 3 }).textContent).toBe("Nhóm con");
    expect(screen.getByRole("listitem").textContent).toBe("gạch đầu dòng");
  });

  it("vẫn render trích dẫn [n] thành nút bấm được khi có headingPrefix", () => {
    const onCitationClick = vi.fn();
    render(
      <div>
        {renderMarkdown("### Nhóm\n1. Làm gì đó [1]", {
          citationCount: 1,
          onCitationClick,
          headingPrefix: () => <i data-testid="icon" />,
        })}
      </div>,
    );

    expect(screen.getByTestId("icon")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "1" })).toBeInTheDocument();
  });

  it("tạo outline đúng thứ tự và ID duy nhất cho heading bị lặp", () => {
    const source = [
      "## Các bước thực hiện",
      "### Chính sách nhân sự",
      "Nội dung A",
      "## Tài liệu nguồn cần đọc",
      "### Chính sách nhân sự",
      "Nội dung B",
    ].join("\n");

    expect(extractMarkdownOutline(source)).toEqual([
      { id: "cac-buoc-thuc-hien", text: "Các bước thực hiện", level: 2, index: 0 },
      { id: "chinh-sach-nhan-su", text: "Chính sách nhân sự", level: 3, index: 1 },
      { id: "tai-lieu-nguon-can-doc", text: "Tài liệu nguồn cần đọc", level: 2, index: 2 },
      { id: "chinh-sach-nhan-su-2", text: "Chính sách nhân sự", level: 3, index: 3 },
    ]);

    render(<div>{renderMarkdown(source)}</div>);
    expect(screen.getAllByRole("heading").map((heading) => heading.id)).toEqual([
      "cac-buoc-thuc-hien",
      "chinh-sach-nhan-su",
      "tai-lieu-nguon-can-doc",
      "chinh-sach-nhan-su-2",
    ]);
  });
});
