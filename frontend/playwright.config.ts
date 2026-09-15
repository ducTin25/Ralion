import { defineConfig, devices } from "@playwright/test";

const isCi = Boolean(process.env.CI);

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: false,
  forbidOnly: isCi,
  retries: isCi ? 2 : 0,
  workers: 1,
  reporter: [["list"]],
  timeout: isCi ? 120_000 : 30_000,
  expect: {
    timeout: isCi ? 20_000 : 5_000,
  },
  use: {
    baseURL: "http://127.0.0.1:3100",
    actionTimeout: isCi ? 20_000 : 0,
    navigationTimeout: isCi ? 30_000 : 0,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "chromium-tablet",
      grep: /@role-ui/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 820, height: 1180 } },
    },
    {
      name: "chromium-390",
      grep: /@role-ui/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 390, height: 844 } },
    },
    {
      name: "webkit-mobile",
      grep: /@mobile-smoke/,
      use: { ...devices["iPhone 13"] },
    },
  ],
  webServer: {
    command: "npm run dev -- --hostname 127.0.0.1 --port 3100",
    url: "http://127.0.0.1:3100/vi/user",
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      API_UPSTREAM_URL: process.env.API_UPSTREAM_URL ?? "http://127.0.0.1:8001",
    },
  },
});
