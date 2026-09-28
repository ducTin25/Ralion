import { expect, test, type Locator, type Page } from "@playwright/test";

const PASSWORD = "ralionralion";

async function signIn(page: Page, email: string) {
  await page.goto("/login");
  await page.locator('input[name="email"]').fill(email);
  await page.locator('input[name="password"]').fill(PASSWORD);
  await page.getByRole("button", { name: "Đăng nhập", exact: true }).click();
  await expect(page).toHaveURL(/\/select-project$/);
}

async function chooseProject(page: Page, name: RegExp) {
  const card = page.getByRole("article").filter({ hasText: name });
  await expect(card).toBeVisible();
  await card.getByRole("button").click();
}

async function expectNoHorizontalOverflow(page: Page) {
  await expect
    .poll(() =>
      page.evaluate(
        () => document.documentElement.scrollWidth <= document.documentElement.clientWidth + 1,
      ),
    )
    .toBe(true);
}

function watchClientErrors(page: Page) {
  const errors: string[] = [];
  page.on("console", (message) => {
    if (
      message.type() === "error" &&
      !message
        .text()
        .startsWith("Failed to load resource: the server responded with a status of 404")
    ) {
      errors.push(message.text());
    }
  });
  page.on("pageerror", (error) => errors.push(error.message));
  page.on("response", (response) => {
    const expectedEmptyState =
      response.status() === 404 &&
      (/\/api\/v1\/onboarding-templates\/pm\/by-project\/\d+$/.test(response.url()) ||
        /\/api\/v1\/onboarding-plans\/pm\/reference\?project_id=\d+$/.test(response.url()));
    if (response.status() >= 400 && !expectedEmptyState) {
      errors.push(`HTTP ${response.status()}: ${response.url()}`);
    }
  });
  return () => expect(errors, "browser console/page errors").toEqual([]);
}

async function pmNavigationTarget(page: Page, name: string): Promise<Locator> {
  const menu = page.getByRole("button", { name: "Mở menu" });
  if (await menu.isVisible()) {
    await menu.click();
    const drawer = page.getByRole("dialog", { name: "Điều hướng Product Manager" });
    await expect(drawer).toBeVisible();
    return drawer.getByRole("button", { name, exact: true });
  }
  return page.getByRole("button", { name, exact: true });
}

async function memberNavigationTarget(page: Page, name: string): Promise<Locator> {
  const menu = page.getByRole("button", { name: "Mở menu" });
  if (await menu.isVisible()) {
    await menu.click();
    const drawer = page.getByRole("dialog", { name: "Điều hướng Engineer Portal" });
    await expect(drawer).toBeVisible();
    return drawer.getByRole("link", { name, exact: true });
  }
  return page.getByRole("link", { name, exact: true });
}

test("@role-ui PM workspace remains actionable from desktop through 390px", async ({ page }) => {
  const expectNoClientErrors = watchClientErrors(page);
  await signIn(page, "pm.phoneshop@onboarding.dev");
  await chooseProject(page, /PhoneShop/);

  await expect(page).toHaveURL(/\/product-manager\?project=\d+/);
  await expect(page.getByRole("heading", { name: "Tổng quan", exact: true })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  const pmRscRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("_rsc=") || request.headers().rsc === "1") {
      pmRscRequests.push(request.url());
    }
  });

  for (const [label, view] of [
    ["Tài liệu dự án", "docs"],
    ["Master Template", "template"],
    ["Onboarding Plan", "plan"],
    ["Thành viên", "members"],
    ["Blocker Engineer", "blockers"],
    ["Duyệt quy ước", "rules"],
  ] as const) {
    await (await pmNavigationTarget(page, label)).click();
    await expect(page).toHaveURL(
      new RegExp(`project=\\d+.*view=${view}|view=${view}.*project=\\d+`),
    );
    await expectNoHorizontalOverflow(page);
  }

  await (await pmNavigationTarget(page, "Tài liệu dự án")).click();
  const scanButton = page.getByRole("button", { name: "Quét repository", exact: true });
  await expect(scanButton).toBeVisible();
  await scanButton.click();
  await expect(page.getByRole("dialog", { name: "Quét repository" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Quét repository" })).toBeHidden();
  await expect(scanButton).toBeFocused();
  expect(pmRscRequests, "PM tab changes must stay client-side").toEqual([]);
  expectNoClientErrors();
});

test("@role-ui Engineer journey preserves project context and dark mode", async ({ page }) => {
  const expectNoClientErrors = watchClientErrors(page);
  await signIn(page, "engineer.phoneshop@onboarding.dev");
  await chooseProject(page, /PhoneShop API/);

  await expect(page).toHaveURL(/\/user\?project=\d+/);
  await expect(page.getByRole("heading", { name: /Xin chào/ })).toBeVisible();
  await expectNoHorizontalOverflow(page);

  const engineerRscRequests: string[] = [];
  page.on("request", (request) => {
    if (request.url().includes("_rsc=") || request.headers().rsc === "1") {
      engineerRscRequests.push(request.url());
    }
  });

  const themeToggle = page.getByRole("button", { name: "Đổi giao diện sáng tối" }).first();
  await themeToggle.click();
  await expect(page.locator('.ralion-workspace[data-theme="dark"]').first()).toBeVisible();
  await expect
    .poll(() => page.evaluate(() => localStorage.getItem("ralion-member-theme")))
    .toBe("dark");

  const taskLink = page.getByRole("link", { name: /Chạy được service ở local/i });
  await expect(taskLink).toBeVisible();
  await taskLink.click();
  await expect(page).toHaveURL(/project=\d+.*task=\d+|task=\d+.*project=\d+/);
  const reportButton = page.getByRole("button", { name: "Báo blocker" });
  await reportButton.click();
  await expect(page.getByRole("dialog", { name: "Tôi đang bị chặn" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("dialog", { name: "Tôi đang bị chặn" })).toBeHidden();
  await expect(reportButton).toBeFocused();
  await expectNoHorizontalOverflow(page);
  await page.getByRole("button", { name: "Quay lại checklist", exact: true }).click();
  await expect(page).not.toHaveURL(/task=/);

  await (await memberNavigationTarget(page, "Quy ước")).click();
  await expect(page).toHaveURL(/project=\d+.*view=conventions|view=conventions.*project=\d+/);
  await expect(page.locator('.ralion-workspace[data-theme="dark"]').first()).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await (await memberNavigationTarget(page, "Ralion Chat")).click();
  await expect(page).toHaveURL(/\/user\?.*view=chat|\/user\?view=chat.*project=\d+/);
  await expect(page.locator('.ralion-workspace[data-theme="dark"]').first()).toBeVisible();
  await expectNoHorizontalOverflow(page);
  expect(engineerRscRequests, "Engineer tab changes must stay client-side").toEqual([]);

  await page.goto("/documents");
  await expect(page.locator('.ralion-workspace[data-theme="dark"]').first()).toBeVisible();
  await expectNoHorizontalOverflow(page);

  await page.goto("/policies");
  await expect(page).toHaveURL(/\/documents$/);
  await expect(page.locator('.ralion-workspace[data-theme="dark"]').first()).toBeVisible();
  expectNoClientErrors();
});
