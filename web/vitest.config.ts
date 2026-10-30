import { defineConfig } from "vitest/config";

/** Unit suite: Playwright owns e2e/, so vitest must not collect it. */
export default defineConfig({
  test: {
    exclude: ["e2e/**", "node_modules/**", ".next/**"],
  },
});
