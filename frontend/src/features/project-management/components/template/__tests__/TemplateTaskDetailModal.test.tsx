import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { TemplateTaskDetailModal } from "@/features/project-management/components/template/TemplateTaskDetailModal";
import type { TaskDependencyResponseDTO } from "@/features/project-management/dto/responseDTO/taskDependency.response";
import type { TemplateTaskResponseDTO } from "@/features/project-management/dto/responseDTO/templateTask.response";

const predecessor: TemplateTaskResponseDTO = {
  template_task_id: 10,
  version_id: 3,
  category: "ORIENTATION",
  title_pattern: "Đọc README dự án",
  objective: "Nắm bối cảnh dự án.",
  instruction_template: "Đọc tài liệu tổng quan.",
  display_order: 1,
  mandatory: true,
  estimated_minutes: 20,
};

const task: TemplateTaskResponseDTO = {
  template_task_id: 11,
  version_id: 3,
  category: "ARCHITECTURE",
  title_pattern: "Tìm hiểu kiến trúc",
  objective: "Hiểu ranh giới và luồng dữ liệu.",
  instruction_template: "Đối chiếu sơ đồ với codebase.",
  display_order: 2,
  mandatory: false,
  estimated_minutes: 45,
};

const dependency: TaskDependencyResponseDTO = {
  dependency_id: 1,
  predecessor_task_id: predecessor.template_task_id,
  successor_task_id: task.template_task_id,
};

describe("TemplateTaskDetailModal", () => {
  it("shows complete read-only task details and resolved dependencies", () => {
    render(
      <TemplateTaskDetailModal
        task={task}
        categoryLabel="Kiến trúc"
        versionNo={1}
        allTasks={[task, predecessor]}
        dependencies={[dependency]}
        onClose={vi.fn()}
      />,
    );

    expect(screen.getByText("Tìm hiểu kiến trúc")).toBeInTheDocument();
    expect(screen.getByText("Kiến trúc")).toBeInTheDocument();
    expect(screen.getByText("Hiểu ranh giới và luồng dữ liệu.")).toBeInTheDocument();
    expect(screen.getByText("Đối chiếu sơ đồ với codebase.")).toBeInTheDocument();
    expect(screen.getByText("Đọc README dự án")).toBeInTheDocument();
    expect(screen.getByText("45 phút")).toBeInTheDocument();
    expect(screen.getByText("Không bắt buộc")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /lưu/i })).not.toBeInTheDocument();
  });
});
