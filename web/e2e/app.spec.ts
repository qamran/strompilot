import { expect, test, type Page } from "@playwright/test";
import { mkdirSync } from "node:fs";
import { join, resolve } from "node:path";

/**
 * Full user journey through the Leitstand. Every test fails on any
 * uncaught page error, because a crashed React tree is exactly the
 * "no button works" symptom from user testing.
 */

const SHOTS = resolve("e2e/screenshots");
mkdirSync(SHOTS, { recursive: true });

const METER_PHOTO = resolve(
  join("..", "api", "tests", "fixtures", "meter", "meter_clean.png"),
);

async function agreeConsent(page: Page, key: "plan" | "photo") {
  const bar = page.getByRole("region", { name: "Consent" });
  await expect(bar).toBeVisible();
  await bar.getByRole("checkbox").check();
  const button = bar.getByRole("button", { name: "I agree" });
  await expect(button).toBeEnabled();
  await button.click();
  await expect(bar).toBeHidden();
  const stored = await page.evaluate(
    (k) => sessionStorage.getItem(`strompilot-consent:${k}`),
    key,
  );
  expect(stored).toBe("1");
}

test.beforeEach(async ({ page }) => {
  const errors: string[] = [];
  page.on("pageerror", (err) => errors.push(String(err)));
  (page as Page & { __errors?: string[] }).__errors = errors;
});

test.afterEach(async ({ page }) => {
  const errors =
    (page as Page & { __errors?: string[] }).__errors ?? [];
  expect(errors, `uncaught page errors: ${errors.join(" | ")}`).toEqual(
    [],
  );
});

test("prices view loads live data", async ({ page }) => {
  await page.goto("/");
  await expect(
    page.getByText("Your power copilot for dynamic tariffs"),
  ).toBeVisible();
  await expect(page.getByText("Right now")).toBeVisible();
  await expect(page.locator("canvas")).toBeVisible();
  await expect(page.getByText("Savings approx.")).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "prices.png") });
});

test("consent remembers the choice for the session", async ({ page }) => {
  await page.goto("/");
  await agreeConsent(page, "plan");
  await page.reload();
  await expect(
    page.getByRole("region", { name: "Consent" }),
  ).toBeHidden();
  await expect(
    page.getByRole("button", { name: "Make a plan" }),
  ).toBeEnabled();
});

test("language toggle switches the whole view", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: "DE", exact: true }).click();
  await expect(page.getByText("Preise").first()).toBeVisible();
  await page.getByRole("button", { name: "EN", exact: true }).click();
  await expect(page.getByText("Prices").first()).toBeVisible();
});

test("command palette opens and navigates", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("ControlOrMeta+k");
  const box = page.getByPlaceholder("Search views or actions …");
  await expect(box).toBeVisible();
  await box.fill("meter");
  await box.press("Enter");
  await expect(page).toHaveURL(/\/zaehler/);
});

test("plan journey completes, approves, and learns", async ({
  page,
}) => {
  test.setTimeout(600_000);
  await page.goto("/");
  await agreeConsent(page, "plan");
  await page
    .getByRole("textbox", { name: "Make a plan" })
    .fill("Night shift, baby sleeps by 10 pm, car must be full by 07:00");
  await page.getByRole("button", { name: "Make a plan" }).click();
  await expect(page).toHaveURL(/\/fahrplan\?thread=/, {
    timeout: 60_000,
  });
  await expect(
    page.getByText("The plan waits for your approval."),
  ).toBeVisible({ timeout: 540_000 });
  await expect(page.locator(".gantt-block").first()).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "fahrplan.png") });
  await page.locator(".gantt-block").first().click();
  const overlay = page.getByRole("dialog", { name: "Why this block?" });
  await expect(overlay).toBeVisible();
  await expect(overlay.getByText(/runs \d\d:\d\d to \d\d:\d\d/)).toBeVisible();
  await page.getByRole("button", { name: "Close" }).click();
  await page.getByRole("button", { name: "Approve" }).click();
  await expect(page.getByText("The plan is approved.")).toBeVisible({
    timeout: 60_000,
  });
  await page
    .getByRole("button", { name: "Just right" })
    .first()
    .click();
  await expect(
    page.getByText("Thanks! The next plan learns from this."),
  ).toBeVisible();
});

test("meter upload reads and confirms", async ({ page }) => {
  await page.goto("/zaehler");
  await agreeConsent(page, "photo");
  const rows = page.locator("section ul li");
  const before = await rows.count();
  await page.locator('input[type="file"]').setInputFiles(METER_PHOTO);
  await page.getByRole("checkbox", { name: "Store the photo" }).check();
  const upload = page.getByRole("button", { name: "Upload photo" });
  await expect(upload).toBeEnabled();
  await upload.click();
  await expect(rows).toHaveCount(before + 1, { timeout: 120_000 });
  const fresh = rows.last();
  await expect(fresh).toContainText("4217.3 kWh");
  await expect(fresh).toContainText("1ESY1162345678");
  await expect(fresh.getByRole("img", { name: /Meter photo/ })).toBeVisible();
  await fresh.getByRole("button", { name: "Confirm" }).click();
  await expect(fresh.getByText("confirmed")).toBeVisible({
    timeout: 60_000,
  });
  await page.screenshot({ path: join(SHOTS, "zaehler.png") });
});

test("alarms trigger a watch", async ({ page }) => {
  await page.goto("/alarme");
  const cards = page.locator(".alert-card");
  const before = await cards.count();
  await page.getByRole("button", { name: "Check now" }).click();
  await expect(page.getByText(/→.*✓/)).toBeVisible({
    timeout: 120_000,
  });
  if ((await cards.count()) > before) {
    await expect(cards.last().getByText("on average")).toBeVisible();
  }
  await page.screenshot({ path: join(SHOTS, "alarme.png") });
});

test("about view renders", async ({ page }) => {
  await page.goto("/ueber");
  await expect(page.getByText("About Strompilot")).toBeVisible();
  await expect(page.getByText("Non-binding orientation").first()).toBeVisible();
  await page.screenshot({ path: join(SHOTS, "ueber.png") });
});
