import { defineConfig, devices } from "@playwright/test";

const useDocker = !!process.env.DOCKER_DEV;

export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: "list",
  use: {
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],
  webServer: useDocker
    ? undefined
    : [
        {
          command:
            "cd .. && WISPGEN_BASE_DOMAIN=localhost LLM_PROVIDER=fake WISPGEN_ENABLE_TEST_ENDPOINTS=1 uv run uvicorn app.main:app --host 0.0.0.0 --port 8000",
          url: "http://localhost:8000/health",
          reuseExistingServer: !process.env.CI,
          timeout: 120 * 1000,
        },
        {
          command: "npm run dev",
          url: "http://localhost:5173",
          reuseExistingServer: !process.env.CI,
          timeout: 120 * 1000,
        },
      ],
  globalSetup: "./e2e/global-setup.ts",
});
