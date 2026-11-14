import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "tests",
  timeout: 60000,
  expect: { timeout: 15000 },
  use: {
    baseURL: process.env.FRONTEND_URL || "http://127.0.0.1:5173",
    viewport: { width: 1440, height: 1080 },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "pnpm dev",
    url: process.env.FRONTEND_URL || "http://127.0.0.1:5173",
    reuseExistingServer: true,
    timeout: 60000,
  },
});
