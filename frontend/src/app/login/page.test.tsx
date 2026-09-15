import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import LoginPage from "./page";

const { login, me, replace } = vi.hoisted(() => ({
  login: vi.fn(),
  me: vi.fn(),
  replace: vi.fn(),
}));

vi.mock("@/i18n/navigation", () => ({
  Link: ({ children, href, ...props }: { children: ReactNode; href: string }) => (
    <a href={href} {...props}>
      {children}
    </a>
  ),
  useRouter: () => ({ replace }),
}));

vi.mock("@/features/auth/session", () => ({
  authApi: { login, me },
}));

vi.mock("@/components/i18n/LanguageSwitcher", () => ({
  LanguageSwitcher: () => <div data-testid="language-switcher" />,
}));

vi.mock("@/components/brand/RalionBrand", () => ({
  RalionBrand: () => <div data-testid="ralion-brand" />,
}));

describe("LoginPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
  });

  it("routes temporary-password accounts to the required password-change flow", async () => {
    login.mockResolvedValue({
      user_id: 42,
      redirect_to: "/change-password",
      outcome: "MUST_CHANGE_PASSWORD",
      expires_at: "2026-08-28T10:00:00Z",
    });
    const user = userEvent.setup();
    render(<LoginPage />);

    await user.type(screen.getByLabelText("Địa chỉ email"), "new.user@example.com");
    await user.type(screen.getByLabelText("Mật khẩu"), "temporary-password");
    await user.click(screen.getByRole("button", { name: "Đăng nhập" }));

    await waitFor(() => expect(replace).toHaveBeenCalledWith("/change-password?required=1"));
    expect(me).not.toHaveBeenCalled();
    expect(window.localStorage.getItem("ralion-demo-user-id")).toBe("42");
  });
});
