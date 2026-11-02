import { defineConfig } from "@playwright/test";

/** Demo-video run: records the scripted tour at 1280x800. */
export default defineConfig({
  testDir: "./e2e",
  testMatch: /demo-video\.spec\.ts/,
  fullyParallel: false,
  workers: 1,
  timeout: 600_000,
  expect: { timeout: 60_000 },
  use: {
    baseURL: "http://127.0.0.1:3100",
    viewport: { width: 1280, height: 800 },
    video: { mode: "on", size: { width: 1280, height: 800 } },
    launchOptions: { slowMo: 250 },
  },
  projects: [{ name: "chromium", use: { browserName: "chromium" } }],
});
