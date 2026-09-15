import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { PmNotificationBell } from "@/features/project-management/components/PmNotificationBell";
import {
  PROJECT_OPERATION_COMPLETED_EVENT,
  type ProjectOperationCompletedDetail,
} from "@/lib/projectOperationNotifications";

function notify(detail: ProjectOperationCompletedDetail) {
  window.dispatchEvent(
    new CustomEvent<ProjectOperationCompletedDetail>(PROJECT_OPERATION_COMPLETED_EVENT, { detail }),
  );
}

describe("PmNotificationBell", () => {
  it("uses the completed operation's persisted document count", async () => {
    render(
      <PmNotificationBell projectId={7} currentUserId={1} />,
    );

    act(() => notify({
      projectId: 7,
      operation: "REPOSITORY_IMPORT",
      status: "SUCCEEDED",
      completedAt: "2026-08-20T10:02:00",
      documentsImported: 5,
    }));

    await userEvent.click(screen.getByRole("button", { name: /thông báo/i }));

    expect(screen.getByText("Đã nhập 5 tài liệu từ thư mục đã quét.")).toBeInTheDocument();
  });

  it("shows PM operation outcomes only, including a backend failure summary", async () => {
    render(
      <PmNotificationBell projectId={7} currentUserId={1} />,
    );

    notify({
      projectId: 7,
      operation: "GITHUB_SYNC",
      status: "FAILED",
      completedAt: "2026-08-20T10:02:00",
      repo: "thanos-io/thanos",
      errorSummary: "GitHub API rate limit exceeded",
    });

    await userEvent.click(screen.getByRole("button", { name: /thông báo/i }));

    expect(screen.getByText("Đồng bộ GitHub chưa hoàn tất.")).toBeInTheDocument();
    expect(screen.getByText("GitHub API rate limit exceeded")).toBeInTheDocument();
    expect(screen.queryByText(/sắp đến hạn|trễ hạn/i)).not.toBeInTheDocument();
  });
});
