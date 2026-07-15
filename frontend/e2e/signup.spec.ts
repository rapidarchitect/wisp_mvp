import { expect, test } from "@playwright/test";

import { apiCallRaw, setStripeMode } from "./api";
import { resetAll } from "./fixtures";

const VOUCHER_CODE = "WISP-2026-DEMO";

async function fillSignupForm(page: any, slug: string, funding: "card" | "voucher") {
  const email = `admin@${slug}.app.wisp.llc`;
  await page.goto(`http://${slug}.localhost:5173/signup`);
  await expect(page.getByText("Create your workspace")).toBeVisible();

  await page.getByLabel("Company name").fill("E2E Signup Firm");
  await page.getByLabel("Address").fill("1 E2E Way");
  await page.getByLabel("Workspace email").fill(email);

  await page.getByRole("radio", { name: funding === "card" ? "Credit card" : "Voucher" }).check();

  if (funding === "voucher") {
    await page.getByLabel("Voucher code").fill(VOUCHER_CODE);
  }

  await page.getByLabel("Employee range").fill("1-10");
  await page.getByLabel("Clients per year range").fill("100-500");
  await page.getByLabel("Primary software").fill("QuickBooks Online");
  await page.getByLabel("Deployment type").fill("cloud");
  await page.getByLabel("IT support provider").fill("Internal IT");
  await page.getByLabel("Coordinator name").fill("E2E Coordinator");
  await page.getByLabel("Coordinator title").fill("Office Manager");
}

test.describe.configure({ mode: "serial" });

test("card signup provisions workspace (SIGN-01)", async ({ page }) => {
  const slug = `e2esignup-${Date.now()}`;

  await fillSignupForm(page, slug, "card");

  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(page.locator("h4")).toContainText("Payment required", { timeout: 10000 });

  await page.click('[data-testid="test-confirm-card"]');
  await expect(page.locator("h4")).toContainText("Workspace ready", { timeout: 10000 });
  await expect(page.locator("text=Your workspace")).toContainText(slug);
});

test("voucher signup skips card payment (SIGN-02)", async ({ page }) => {
  const slug = `e2evoucher-${Date.now()}`;

  await fillSignupForm(page, slug, "voucher");
  await page.getByRole("button", { name: "Create workspace" }).click();

  await expect(page.locator("h4")).toContainText("Workspace ready", { timeout: 10000 });
  await expect(page.locator("text=Your workspace")).toContainText(slug);
});

test("declined card leaves no workspace (SIGN-03)", async ({ page, request }) => {
  await setStripeMode("decline");
  const slug = `e2edecline-${Date.now()}`;

  await fillSignupForm(page, slug, "card");
  await page.getByRole("button", { name: "Create workspace" }).click();

  // The UI surfaces a generic signup error because the backend raises.
  await expect(page.getByText(/Signup failed|Your card was declined/)).toBeVisible({ timeout: 10000 });

  // The tenant should not exist; any non-signup API call returns 404 from the middleware.
  const probe = await request.get(`http://${slug}.localhost:8000/api/v1/auth/me`, {
    headers: { Authorization: "Bearer dummy" },
  });
  expect(probe.status()).toBe(404);

  await setStripeMode("succeed");
});

test("workspace address must be unique (SIGN-04)", async ({ page }) => {
  const slug = `e2eunique-${Date.now()}`;

  // First signup with card, confirm payment, so the workspace exists.
  await fillSignupForm(page, slug, "card");
  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(page.locator("h4")).toContainText("Payment required", { timeout: 10000 });
  await page.click('[data-testid="test-confirm-card"]');
  await expect(page.locator("h4")).toContainText("Workspace ready", { timeout: 10000 });

  // Second signup with the same slug should be rejected.
  await page.goto(`http://${slug}.localhost:5173/signup`);
  await expect(page.getByText("Create your workspace")).toBeVisible();
  await page.getByLabel("Company name").fill("Duplicate Firm");
  await page.getByLabel("Address").fill("2 E2E Way");
  await page.getByLabel("Workspace email").fill(`admin2@${slug}.app.wisp.llc`);
  await page.getByRole("radio", { name: "Voucher" }).check();
  await page.getByLabel("Voucher code").fill(VOUCHER_CODE);
  await page.getByLabel("Employee range").fill("1-10");
  await page.getByLabel("Clients per year range").fill("100-500");
  await page.getByLabel("Primary software").fill("QuickBooks Online");
  await page.getByLabel("Deployment type").fill("cloud");
  await page.getByLabel("IT support provider").fill("Internal IT");
  await page.getByLabel("Coordinator name").fill("E2E Coordinator");
  await page.getByLabel("Coordinator title").fill("Office Manager");
  await page.getByRole("button", { name: "Create workspace" }).click();

  await expect(page.getByText(/already taken|slug_taken/)).toBeVisible({ timeout: 10000 });
});

test("corporate vitals validation rejects empty coordinator (SIGN-05)", async ({ page }) => {
  const slug = `e2evitals-${Date.now()}`;
  await page.goto(`http://${slug}.localhost:5173/signup`);
  await expect(page.getByText("Create your workspace")).toBeVisible();

  await page.getByLabel("Company name").fill("E2E Signup Firm");
  await page.getByLabel("Address").fill("1 E2E Way");
  await page.getByLabel("Workspace email").fill(`admin@${slug}.app.wisp.llc`);
  await page.getByRole("radio", { name: "Voucher" }).check();
  await page.getByLabel("Voucher code").fill(VOUCHER_CODE);

  await page.getByLabel("Employee range").fill("1-10");
  await page.getByLabel("Clients per year range").fill("100-500");
  await page.getByLabel("Primary software").fill("QuickBooks Online");
  await page.getByLabel("Deployment type").fill("cloud");
  await page.getByLabel("IT support provider").fill("Internal IT");
  // Leave coordinator name blank and clear the pre-filled title.
  await page.getByLabel("Coordinator name").fill("");
  await page.getByLabel("Coordinator title").fill("");

  await page.getByRole("button", { name: "Create workspace" }).click();

  // Browser validation (required fields) prevents submission; we remain on the form.
  await expect(page.getByText("Create your workspace")).toBeVisible();
  await expect(page.locator("h4")).not.toContainText("Workspace ready");
});
