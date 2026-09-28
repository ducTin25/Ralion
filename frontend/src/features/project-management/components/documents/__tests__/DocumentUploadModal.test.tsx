import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { DocumentUploadModal } from "@/features/project-management/components/documents/DocumentUploadModal";

vi.mock("@/features/project-management/api", () => ({
  uploadProjectDocument: vi.fn(),
}));

function pickFile(name: string, type: string) {
  const input = document.querySelector<HTMLInputElement>('input[type="file"]');
  if (!input) throw new Error("Document file input was not rendered");
  fireEvent.change(input, { target: { files: [new File(["noi dung"], name, { type })] } });
}

// Trước fix, tiêu đề chỉ tự điền khi còn rỗng: đổi file (pet_project.docx -> thesis.md) thì tên
// file cũ vẫn nằm nguyên trên form và được gửi lên làm `title` của tài liệu.
describe("DocumentUploadModal — đổi file đã chọn", () => {
  it("cập nhật cả tên file lẫn tiêu đề khi chọn file khác", () => {
    render(
      <DocumentUploadModal
        projectId={1}
        defaultCategory="SETUP"
        onClose={() => {}}
        onSaved={() => {}}
      />,
    );

    pickFile("pet_project.docx", "application/vnd.openxmlformats-officedocument");
    expect(screen.getByText("pet_project.docx")).toBeInTheDocument();
    expect(screen.getByDisplayValue("pet_project.docx")).toBeInTheDocument();

    pickFile("thesis.md", "text/markdown");
    expect(screen.getByText("thesis.md")).toBeInTheDocument();
    expect(screen.getByDisplayValue("thesis.md")).toBeInTheDocument();
    expect(screen.queryByText("pet_project.docx")).not.toBeInTheDocument();
    expect(screen.queryByDisplayValue("pet_project.docx")).not.toBeInTheDocument();
  });

  it("giữ nguyên tiêu đề PM đã tự gõ khi đổi file", () => {
    render(
      <DocumentUploadModal
        projectId={1}
        defaultCategory="SETUP"
        onClose={() => {}}
        onSaved={() => {}}
      />,
    );

    pickFile("pet_project.docx", "application/vnd.openxmlformats-officedocument");
    fireEvent.change(screen.getByLabelText("Tiêu đề tài liệu"), {
      target: { value: "Huong dan cai dat" },
    });

    pickFile("thesis.md", "text/markdown");
    expect(screen.getByText("thesis.md")).toBeInTheDocument();
    expect(screen.getByDisplayValue("Huong dan cai dat")).toBeInTheDocument();
  });
});
