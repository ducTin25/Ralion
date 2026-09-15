import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { AccountChatPreferences } from "@/features/auth/AccountChatPreferences";

function renderControl(onUpdate = vi.fn().mockResolvedValue(undefined)) {
  render(
    <AccountChatPreferences
      binding={{ responseLength: "STANDARD", responseTone: "NEUTRAL", onUpdate }}
    />,
  );
  return onUpdate;
}

describe("Account chat preferences", () => {
  it("persists a length change server-side using the backend preset enum", async () => {
    const onUpdate = renderControl();

    await userEvent.click(screen.getByRole("button", { name: /Response preferences/ }));
    await userEvent.selectOptions(screen.getByLabelText("Length"), "CONCISE");

    expect(onUpdate).toHaveBeenCalledWith({ response_length: "CONCISE" });
  });

  it("persists a tone change server-side without touching the other field", async () => {
    const onUpdate = renderControl();

    await userEvent.click(screen.getByRole("button", { name: /Response preferences/ }));
    await userEvent.selectOptions(screen.getByLabelText("Tone"), "MENTOR");

    expect(onUpdate).toHaveBeenCalledWith({ response_tone: "MENTOR" });
  });

  it("offers only the backend presets and no free-text instruction field", async () => {
    renderControl();
    await userEvent.click(screen.getByRole("button", { name: /Response preferences/ }));

    const lengths = screen.getByLabelText("Length") as HTMLSelectElement;
    const tones = screen.getByLabelText("Tone") as HTMLSelectElement;
    expect([...lengths.options].map((option) => option.value)).toEqual([
      "CONCISE",
      "STANDARD",
      "DETAILED",
    ]);
    expect([...tones.options].map((option) => option.value)).toEqual([
      "NEUTRAL",
      "GUIDE",
      "MENTOR",
      "BUDDY",
    ]);
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });

  it("reflects the saved preference rather than a local copy", async () => {
    renderControl();
    await userEvent.click(screen.getByRole("button", { name: /Response preferences/ }));

    // Giá trị hiển thị đến từ prop (state phiên), không phải state cục bộ — chọn xong mà server
    // chưa xác nhận thì select vẫn giữ giá trị đã lưu.
    await userEvent.selectOptions(screen.getByLabelText("Length"), "DETAILED");
    expect((screen.getByLabelText("Length") as HTMLSelectElement).value).toBe("STANDARD");
  });

  it("reports a failed save instead of pretending it persisted", async () => {
    renderControl(vi.fn().mockRejectedValue(new Error("network down")));

    await userEvent.click(screen.getByRole("button", { name: /Response preferences/ }));
    await userEvent.selectOptions(screen.getByLabelText("Length"), "CONCISE");

    await waitFor(() =>
      expect(screen.getByRole("alert")).toHaveTextContent(/save your preferences/i),
    );
  });
});
