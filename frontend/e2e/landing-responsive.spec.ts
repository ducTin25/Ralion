import { expect, test, type Page } from "@playwright/test";

const viewports = [
  { width: 360, height: 800 },
  { width: 390, height: 844 },
  { width: 768, height: 1024 },
  { width: 1024, height: 768 },
  { width: 1440, height: 900 },
] as const;

const locales = [
  { locale: "vi", heading: "Giúp mọi kỹ sư hiểu đội ngũ nhanh hơn." },
  { locale: "en", heading: "Help Every Engineer Understand Teams Faster." },
] as const;

async function landingLayout(page: Page) {
  return page.evaluate(() => {
    const hero = document.querySelector<HTMLElement>("main > section");
    const knowledgeMap = document.querySelector<HTMLElement>(
      'main > section#hero [class*="heroVisual"]',
    );
    if (!hero || !knowledgeMap) throw new Error("Landing hero or knowledge map is missing");
    const heroBounds = hero.getBoundingClientRect();
    const mapBounds = knowledgeMap.getBoundingClientRect();
    return {
      clientWidth: document.documentElement.clientWidth,
      scrollWidth: document.documentElement.scrollWidth,
      heroLeft: heroBounds.left,
      heroRight: heroBounds.right,
      mapLeft: mapBounds.left,
      mapRight: mapBounds.right,
    };
  });
}

for (const { locale, heading } of locales) {
  for (const viewport of viewports) {
    test(`${locale} landing stays within ${viewport.width}px`, async ({ page }) => {
      const consoleErrors: string[] = [];
      page.on("console", (message) => {
        if (message.type() === "error") consoleErrors.push(message.text());
      });
      page.on("pageerror", (error) => consoleErrors.push(error.message));

      await page.setViewportSize(viewport);
      await page.goto(`/${locale}`);
      await expect(page.getByRole("heading", { name: heading })).toBeVisible();
      await expect(page.locator('main > section#hero [class*="heroVisual"]')).toBeVisible();

      const layout = await landingLayout(page);
      expect(layout.scrollWidth).toBeLessThanOrEqual(layout.clientWidth + 1);
      expect(layout.heroLeft).toBeGreaterThanOrEqual(-1);
      expect(layout.heroRight).toBeLessThanOrEqual(layout.clientWidth + 1);
      expect(layout.mapLeft).toBeGreaterThanOrEqual(-1);
      expect(layout.mapRight).toBeLessThanOrEqual(layout.clientWidth + 1);
      expect(consoleErrors).toEqual([]);
    });
  }
}

test("@mobile-smoke public pages fit at 320px", async ({ page }) => {
  await page.setViewportSize({ width: 320, height: 720 });
  for (const path of ["/vi", "/vi/login", "/vi/access-denied", "/en", "/en/login"]) {
    await page.goto(path);
    const widths = await page.evaluate(() => ({
      client: document.documentElement.clientWidth,
      scroll: document.documentElement.scrollWidth,
    }));
    expect(widths.scroll, path).toBeLessThanOrEqual(widths.client + 1);
  }
});

test("language switcher preserves path and query", async ({ page }) => {
  await page.goto("/vi/login?next=%2Fvi%2Fadmin%3Fpage%3D2");
  await page.locator("summary[aria-label^='Ngôn ngữ']").click();
  await page.getByRole("menuitem", { name: "English", exact: true }).click();
  await expect(page).toHaveURL(/\/en\/login\?next=%2Fvi%2Fadmin%3Fpage%3D2$/);
  await expect(page.getByRole("heading", { name: "Sign in to Ralion" })).toBeAttached();
});

test("landing navigation scrolls to the walkthrough", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/en");
  await page.getByRole("link", { name: "How It Works", exact: true }).first().click();
  await expect(page).toHaveURL(/\/en#how$/);
  await expect(
    page.getByRole("heading", { name: "Shorten the time from day one to first contribution." }),
  ).toBeVisible();
});

test("login exposes the test account guide", async ({ page }) => {
  await page.goto("/vi/login");

  const guide = page.getByRole("link", {
    name: "Mở hướng dẫn tài khoản test trong thẻ mới",
  });
  await expect(guide).toBeVisible();
  await expect(guide).toHaveAttribute(
    "href",
    "https://docs.google.com/document/d/1dEuJ5dLvXXm8esvwbvrxKgABAFuTjTYW30x1NfNYx1s/edit?tab=t.0",
  );
  await expect(guide).toHaveAttribute("target", "_blank");

  const widths = await page.evaluate(() => ({
    client: document.documentElement.clientWidth,
    scroll: document.documentElement.scrollWidth,
  }));
  expect(widths.scroll).toBeLessThanOrEqual(widths.client + 1);
});
