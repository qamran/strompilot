import { expect, test } from "@playwright/test";
import { join } from "node:path";

/**
 * Scripted demo tour for the release video. Runs only with DEMO_VIDEO=1
 * so the normal suite stays fast. Beats follow docs/demo/script.md.
 * The tour plans live and falls back to the seeded thread only when
 * the run stalls, so a bad take never blocks the recording.
 */
test.skip(
  process.env.DEMO_VIDEO !== "1",
  "demo recording only",
);

const THREAD = "16121e2d24cc44c48572ab29446cd4f7";
const HOUSE = join(__dirname, "fixtures", "house.png");
const SENTENCE = "Night shift, the baby sleeps by 8pm, the car must be full by 6am";

test("demo tour", async ({ page }) => {
  test.setTimeout(600_000);

  // Beat 1 — sign in, under three seconds of attention (0:00-0:10).
  await page.goto("/signin");
  await page
    .getByRole("textbox", { name: "Email address" })
    .fill("demo@example.de");
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Send link" }).click();
  await page.getByTestId("dev-link").click();
  await expect(page).toHaveURL(/\/account/);
  await page.waitForTimeout(7000);

  // Beat 2 — today at a glance (0:10-0:30).
  await page.goto("/");
  await expect(
    page.getByText("Your power copilot for dynamic tariffs"),
  ).toBeVisible();
  await expect(page.getByText("Planning consent agreed.")).toBeVisible();
  await expect(page.locator("section.hero").getByText("Right now")).toBeVisible();
  await page.waitForTimeout(6000);
  await page.mouse.wheel(0, 500);
  await expect(page.getByText("Today at a glance")).toBeVisible();
  await page.waitForTimeout(10000);

  // Beat 3 — the live plan (0:30-2:00).
  await page.goto("/");
  await page.getByRole("textbox", { name: "Make a plan" }).fill(SENTENCE);
  await page.getByRole("button", { name: "Make a plan" }).click();
  await expect(page).toHaveURL(/\/plan\?thread=/, { timeout: 60_000 });
  const trace = page.locator('section[aria-label="Live agent trace"]');
  await expect(trace.locator(".steps-live li").first()).toBeVisible({
    timeout: 120_000,
  });
  await expect(trace.locator(".step-model").first()).toBeVisible({
    timeout: 120_000,
  });
  await page.waitForTimeout(10000);
  let live = true;
  try {
    await expect(
      page.getByText("The plan waits for your approval."),
    ).toBeVisible({ timeout: 420_000 });
  } catch {
    live = false;
    await page.goto(`/plan?thread=${THREAD}`);
  }
  await expect(page.locator(".gantt-block").first()).toBeVisible({
    timeout: 60_000,
  });
  await page.waitForTimeout(6000);
  await page.locator(".gantt-block").first().click();
  const overlay = page.getByRole("dialog", { name: "Why this block?" });
  await expect(overlay).toBeVisible();
  await page.waitForTimeout(8000);
  await page.getByRole("button", { name: "Close" }).click();
  if (live) {
    await page.getByRole("button", { name: "Approve" }).click();
    await expect(page.getByText("The plan is approved.")).toBeVisible({
      timeout: 60_000,
    });
    await expect(trace.getByText("Program wallbox")).toBeVisible({
      timeout: 120_000,
    });
    await trace.getByText("Program wallbox").scrollIntoViewIfNeeded();
    await page.waitForTimeout(6000);
  } else {
    await expect(page.getByText("The plan is approved.")).toBeVisible();
    await trace.scrollIntoViewIfNeeded();
    await page.waitForTimeout(6000);
  }

  // Beat 4 — meter truth (2:00-2:15).
  await page.goto("/meter");
  await expect(page.getByText("4,217.3").first()).toBeVisible({ timeout: 60_000 });
  await page.waitForTimeout(12000);

  // Beat 5 — alarms (2:15-2:25).
  await page.goto("/alarms");
  await expect(page.getByText("Delivered via").first()).toBeVisible({
    timeout: 60_000,
  });
  await page.waitForTimeout(8000);

  // Beat 6 — household (2:25-2:33).
  await page.goto("/household");
  await expect(page.getByText("washing machine").first()).toBeVisible({
    timeout: 60_000,
  });
  await page.locator('section[aria-label="Consent"]').scrollIntoViewIfNeeded();
  await page.waitForTimeout(11000);

  // Beat 7 — solar teaser (2:33-2:52).
  await page.goto("/solar");
  await expect(page.getByText("Planning consent agreed.")).toBeVisible();
  await page
    .getByLabel("House photo", { exact: true })
    .setInputFiles(HOUSE);
  await page.getByLabel(/Roof width/).fill("12");
  await page.getByRole("button", { name: "Measure roof" }).click();
  await expect(page.getByText("Panels", { exact: true })).toBeVisible({
    timeout: 120_000,
  });
  await page.waitForTimeout(12000);

  // Beat 8 — close (2:52-3:00).
  await page.goto("/about");
  await expect(page.getByText("About Strompilot")).toBeVisible();
  await page.waitForTimeout(8000);
});
