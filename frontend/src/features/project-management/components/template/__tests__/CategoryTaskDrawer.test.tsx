import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { CategoryTaskDrawer } from "@/features/project-management/components/template/CategoryTaskDrawer";
import type { TemplateTaskResponseDTO } from "@/features/project-management/dto/responseDTO/templateTask.response";

const task: TemplateTaskResponseDTO = {
  template_task_id: 11,
  version_id: 3,
  category: "ORIENTATION",
  title_pattern: "Đọc tài liệu Overview dự án",
  objective: "Hiểu mục tiêu và phạm vi dự án.",
  instruction_template: "Đọc README và ghi lại các thành phần chính.",
  display_order: 2,
  mandatory: true,
  estimated_minutes: 30,
};

function renderDrawer({ isDraft = false } = {}) {
  const handlers = {
    onView: vi.fn(),
    onEdit: vi.fn(),
    onDelete: vi.fn(),
    onClose: vi.fn(),
    onAddNew: vi.fn(),
  };
  render(
    <CategoryTaskDrawer
      categoryLabel="Tổng quan dự án"
      versionNo={1}
      tasks={[task]}
      isDraft={isDraft}
      {...handlers}
    />,
  );
  return handlers;
}

describe("CategoryTaskDrawer", () => {
  it("opens a read-only task from version history by click and keyboard", async () => {
    const user = userEvent.setup();
    const handlers = renderDrawer();
    const taskCard = screen.getByRole("button", { name: /Đọc tài liệu Overview dự án/i });

    await user.click(taskCard);
    expect(handlers.onView).toHaveBeenCalledWith(task);
    expect(screen.queryByTitle("Sửa")).not.toBeInTheDocument();
    expect(screen.queryByTitle("Xóa")).not.toBeInTheDocument();

    fireEvent.keyDown(taskCard, { key: "Enter" });
    fireEvent.keyDown(taskCard, { key: " " });
    expect(handlers.onView).toHaveBeenCalledTimes(3);
  });

  it("keeps draft edit and delete actions separate from viewing", async () => {
    const user = userEvent.setup();
    const handlers = renderDrawer({ isDraft: true });

    await user.click(screen.getByTitle("Sửa"));
    expect(handlers.onEdit).toHaveBeenCalledWith(task);
    expect(handlers.onView).not.toHaveBeenCalled();

    await user.click(screen.getByTitle("Xóa"));
    expect(handlers.onDelete).toHaveBeenCalledWith(task);
    expect(handlers.onView).not.toHaveBeenCalled();
  });
});
