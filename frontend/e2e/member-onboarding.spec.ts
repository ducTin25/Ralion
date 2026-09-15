import { expect, test, type Page } from "@playwright/test";

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill("ralionralion");
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
}

test("engineer completes the onboarding portal journey", async ({ page }) => {
  await signIn(page, "engineer.phoneshop@onboarding.dev");

  await expect(page).toHaveURL(/\/select-project$/);
  const projectCard = page.getByRole("article").filter({ hasText: "PhoneShop API" });
  await projectCard.getByRole("button").click();
  await expect(page).toHaveURL(/\/user\?project=\d+$/);
  await expect(page.getByRole("heading", { name: "Chọn dự án", exact: true })).toHaveCount(0);
  await expect(page.getByRole("combobox", { name: "Đổi dự án" })).toBeVisible();

  await expect(page.getByRole("heading", { name: "Xin chào Nguyễn Văn A" })).toBeVisible();
  await expect(page.getByLabel(/Tiến độ \d+%/)).toContainText(/\d+\/\d+ task/);

  await page.getByRole("link", { name: /Chạy được service ở local/i }).click();
  await expect(page).toHaveURL(/task=\d+/);
  const taskDetail = page.getByRole("region", { name: /Chạy được service ở local/i });
  await expect(taskDetail).toBeVisible();
  await taskDetail.getByRole("button", { name: "Báo blocker" }).click();

  const blockerModal = page.getByRole("dialog", { name: "Tôi đang bị chặn" });
  await blockerModal.getByRole("combobox", { name: "Loại blocker" }).selectOption("TECHNICAL");
  await blockerModal
    .getByRole("textbox", { name: "Mô tả vấn đề" })
    .fill("E2E: service local không kết nối được database sau khi chạy Docker.");
  await blockerModal.getByRole("button", { name: "Báo blocker", exact: true }).click();
  await expect(page.getByText("Đã ghi nhận blocker.")).toBeVisible();
  await taskDetail.getByRole("button", { name: "Quay lại checklist", exact: true }).click();
  await expect(page).not.toHaveURL(/task=/);

  await page.getByRole("link", { name: /Blocker của tôi/i }).click();
  await expect(page).toHaveURL(/view=blockers/);
  await expect(
    page.getByText("E2E: service local không kết nối được database sau khi chạy Docker."),
  ).toBeVisible();

  await page.getByRole("link", { name: "Checklist & Plan" }).click();
  await page.getByRole("link", { name: /Đọc Codebase Guide/i }).click();
  const codebaseDetail = page.getByRole("region", { name: /Đọc Codebase Guide/i });
  await codebaseDetail.getByRole("button", { name: "Bắt đầu task" }).click();
  await expect(
    codebaseDetail.locator("span").getByText("Đang thực hiện", { exact: true }),
  ).toBeVisible();
  await page.goBack();
  await expect(codebaseDetail).toBeHidden();
  await expect(page).not.toHaveURL(/task=/);

  await expect(page.getByText("First Task & First PR", { exact: true })).toHaveCount(0);

  await page
    .getByRole("combobox", { name: "Đổi dự án" })
    .selectOption({ label: "TourBooking Service" });
  await expect(page.getByText(/TourBooking Service/).first()).toBeVisible();
  await expect(page).toHaveURL(/project=\d+/);

  await page.goto("/user");
  await expect(page).toHaveURL(/\/select-project$/);
});

test("a user with one active membership still lands on Select Project after login", async ({
  page,
}) => {
  await signIn(page, "pm.phoneshop@onboarding.dev");

  await expect(page).toHaveURL(/\/select-project$/);
  const projectCard = page.getByRole("article").filter({ hasText: "PhoneShop" });
  await projectCard.getByRole("button").click();
  await expect(page).toHaveURL(/\/product-manager\?project=\d+$/);
});
