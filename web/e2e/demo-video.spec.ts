import { expect, test, type Page } from "@playwright/test";
import { join } from "node:path";

/**
 * Scripted demo tour for the SP-16 video. Runs only with DEMO_VIDEO=1
 * so the normal suite stays fast. Beats follow docs/demo/script.md.
 */
test.skip(
  process.env.DEMO_VIDEO !== "1",
  "demo recording only",
);

const THREAD = "914f97b011994a5c869a75b79d3c240d";
const HOUSE = join(__dirname, "fixtures", "house.png");

async function agreeConsent(page: Page) {
  const bar = page.getByRole("region", { name: "Consent" });
  await bar.getByRole("checkbox").check();
  await bar.getByRole("button", { name: "I agree" }).click();
  await expect(bar).toBeHidden();
}

test("demo tour", async ({ page }) => {
  // Beat 1 — sign in (0:00-0:20).
  await page.goto("/signin");
  await page.waitForTimeout(2000);
  await page
    .getByRole("textbox", { name: "Email address" })
    .fill("demo@example.de");
  await page.getByRole("button", { name: "Send link" }).click();
  await page.getByTestId("dev-link").click();
  await expect(page).toHaveURL(/\/account/);
  await expect(page.getByText("demo@example.de")).toBeVisible();
  await page.waitForTimeout(8000);

  // Beat 2 — live prices (0:20-0:50).
  await page.goto("/");
  await expect(
    page.getByText("Your power copilot for dynamic tariffs"),
  ).toBeVisible();
  await page.waitForTimeout(8000);
  await page.mouse.wheel(0, 500);
  await page.waitForTimeout(11000);
  await page.mouse.wheel(0, 500);
  await page.waitForTimeout(9000);

  // Beat 3 — the plan (0:50-1:35).
  await page.goto(`/plan?thread=${THREAD}`);
  await expect(page.locator(".gantt-block").first()).toBeVisible({
    timeout: 60000,
  });
  await expect(page.getByText("The plan is approved.")).toBeVisible();
  await page.waitForTimeout(8000);
  await page.locator(".gantt-block").first().click();
  await expect(
    page.getByRole("dialog", { name: "Why this block?" }),
  ).toBeVisible();
  await page.waitForTimeout(11000);
  await page.getByRole("button", { name: "Close" }).click();
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(10000);
  await page.mouse.wheel(0, 600);
  await page.waitForTimeout(9000);

  // Beat 4 — meter truth (1:35-1:55).
  await page.goto("/meter");
  await expect(page.getByText("4217.3")).toBeVisible({ timeout: 60000 });
  await page.waitForTimeout(11000);

  // Beat 5 — alarms (1:55-2:10).
  await page.goto("/alarms");
  await expect(page.getByText("Delivered via").first()).toBeVisible({
    timeout: 60000,
  });
  await page.waitForTimeout(11000);

  // Beat 6 — household (2:10-2:22).
  await page.goto("/household");
  await expect(page.getByText("Waschmaschine").first()).toBeVisible({
    timeout: 60000,
  });
  await page.waitForTimeout(11000);

  // Beat 7 — solar teaser (2:22-2:48).
  await page.goto("/solar");
  await agreeConsent(page);
  await page
    .getByLabel("House photo", { exact: true })
    .setInputFiles(HOUSE);
  await page.getByLabel(/Roof width/).fill("12");
  await page.getByRole("button", { name: "Measure roof" }).click();
  await expect(page.getByText("Panels", { exact: true })).toBeVisible({
    timeout: 120000,
  });
  await page.waitForTimeout(14000);

  // Beat 8 — close (2:48-3:00).
  await page.goto("/about");
  await page.waitForTimeout(10000);
});
