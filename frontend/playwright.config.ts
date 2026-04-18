import { defineConfig } from "@playwright/test";

// Playwright drives the real frontend + real backend (both local).
// webServer spawns uvicorn and vite before tests. For CI, install
// browsers via `npx playwright install chromium` (handled in the
// workflow when e2e enables).

export default defineConfig({
  testDir: "./e2e",
  timeout: 30_000,
  fullyParallel: false,
  use: {
    baseURL: "http://localhost:5173",
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "cd ../backend && uv run uvicorn poker_coach.main:app --port 8000",
      url: "http://localhost:8000/api/health",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: !process.env.CI,
      timeout: 60_000,
    },
  ],
});
