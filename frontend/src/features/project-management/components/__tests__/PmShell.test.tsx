import { fireEvent, render, screen } from "@testing-library/react";
import type { AnchorHTMLAttributes, ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { PmShell } from "@/features/project-management/components/PmShell";

vi.mock("@/features/project-management/components/PmNotificationBell", () => ({
  PmNotificationBell: () => <button type="button">Notifications</button>,
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({
    href,
    children,
    ...props
  }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string; children: ReactNode }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
  usePathname: () => "/product-manager",
  useRouter: () => ({ replace: vi.fn() }),
}));

vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

const currentUser = {
  user_id: 11,
  display_name: "PM Test",
  email: "pm@example.test",
  system_role: null,
  status: "ACTIVE" as const,
  response_length: "STANDARD" as const,
  response_tone: "NEUTRAL" as const,
  memberships: [],
  expires_at: null,
};

describe("PmShell", () => {
  it("uses the scoped modern workspace and keeps navigation behavior unchanged", () => {
    const onNavigate = vi.fn();
    const { container } = render(
      <PmShell
        active="overview"
        crumb="Tổng quan"
        currentUser={currentUser}
        onNavigate={onNavigate}
        onSignOut={vi.fn()}
        switchProjectHref="/select-project"
      >
        <h1>Dashboard content</h1>
      </PmShell>,
    );

    expect(container.querySelector(".ralion-workspace")).toBeInTheDocument();
    expect(screen.getAllByLabelText("Ralion")[0]).toHaveAttribute("href", "/");
    expect(screen.getByText("Dashboard content")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /Tài liệu dự án/ }));
    expect(onNavigate).toHaveBeenCalledWith("docs");
  });
});
