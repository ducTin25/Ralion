import { render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { DocumentPreviewModal } from "@/features/project-management/components/ui/DocumentPreviewModal";

// Tài liệu dự án `.docx`/`.pdf`, hoặc tài liệu đến từ GitHub, không có cách nào đọc bằng cách tự
// tải `sourceUrl` trong trình duyệt: link Cloudinary vướng CORS, link GitHub là trang blob HTML,
// còn DOCX thì trình duyệt không render được. Backend giờ trả markdown đã chuẩn hoá qua
// `fetchContent`, và modal phải đọc từ đó — không fetch mạng, không đẩy PM ra tab ngoài.
describe("DocumentPreviewModal — nội dung do backend cung cấp", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  it("hiển thị markdown từ fetchContent với tài liệu .docx, không tự tải sourceUrl", async () => {
    render(
      <DocumentPreviewModal
        title="pet_project.docx"
        sourceUrl="https://res.cloudinary.com/demo/raw/upload/pet_project.docx"
        fetchContent={async () => "# Tong quan du an\n\nBackend FastAPI, frontend Next.js."}
        onClose={() => {}}
      />,
    );

    expect(await screen.findByText("Tong quan du an")).toBeInTheDocument();
    expect(screen.getByText(/Backend FastAPI/)).toBeInTheDocument();
    expect(fetch).not.toHaveBeenCalled();
    expect(screen.queryByText("Mở trong tab mới")).not.toBeInTheDocument();
    expect(screen.queryByText(/Không thể xem trước/)).not.toBeInTheDocument();
  });

  it("vẫn cho mở bản gốc khi tải nội dung lỗi", async () => {
    render(
      <DocumentPreviewModal
        title="setup_guide.pdf"
        sourceUrl="https://res.cloudinary.com/demo/raw/upload/setup_guide.pdf"
        fetchContent={async () => {
          throw new Error("HTTP 500");
        }}
        onClose={() => {}}
      />,
    );

    await waitFor(() =>
      expect(screen.getByText("Không thể tải nội dung xem trước.")).toBeInTheDocument(),
    );
    expect(screen.getByText("Mở trong tab mới")).toBeInTheDocument();
  });
});
