import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";

const isCi = Boolean(process.env.CI);

export default defineConfig({
  plugins: [react()],
  resolve: {
    tsconfigPaths: true,
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
    exclude: ["e2e/**", "node_modules/**"],
    // The self-hosted CI runner has limited CPU. Serializing jsdom files avoids
    // user-event starvation while keeping the stricter local timeout.
    fileParallelism: !isCi,
    testTimeout: isCi ? 20_000 : 5_000,
    hookTimeout: isCi ? 20_000 : 10_000,
  },
});
