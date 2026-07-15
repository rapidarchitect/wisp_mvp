import { expect, test } from "@playwright/test";

import { apiCallRaw, loginAsApi, testLogin } from "../api";
import { resetAll } from "../fixtures";

const ADMIN_EMAIL = "admin@demo.example.com";
const ADMIN_TOTP = "otpauth://totp/WISPGen:admin%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen";
const CONTRIBUTOR_EMAIL = "contributor@demo.example.com";
const REVIEWER_EMAIL = "reviewer@demo.example.com";
const CODE = "AC";

const SCREENSHOT_DIR = "../docs/generated/screenshots";

test.beforeEach(async ({ request }) => {
  await resetAll(request);
});

test("capture dashboard, users, domains, questionnaire, and review screenshots", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });

  await loginAsApi(page, ADMIN_EMAIL, ADMIN_TOTP);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  await page.screenshot({ path: `${SCREENSHOT_DIR}/dashboard.png`, fullPage: true });

  await page.getByRole("link", { name: "Users" }).click();
  await expect(page.getByRole("heading", { name: "Users and invitations" })).toBeVisible();
  await page.getByLabel("Email").fill("manual-screenshot@demo.example.com");
  await page.getByRole("combobox", { name: "Roles" }).click();
  await page.getByRole("option", { name: "contributor" }).click();
  await page.keyboard.press("Escape");
  await page.screenshot({ path: `${SCREENSHOT_DIR}/users-page.png`, fullPage: true });

  await page.getByRole("link", { name: "Domains" }).click();
  await expect(page.getByRole("heading", { name: "Domains" })).toBeVisible();
  await page.screenshot({ path: `${SCREENSHOT_DIR}/domains-page.png`, fullPage: true });

  // Assign AC so it shows in contributor/reviewer views.
  const adminToken = await testLogin(ADMIN_EMAIL);
  await apiCallRaw(`/domains/${CODE}/assign`, {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({
      contributor_email: CONTRIBUTOR_EMAIL,
      reviewer_email: REVIEWER_EMAIL,
    }),
  });
  await page.reload();
  await expect(page.getByTestId("domain-card-AC")).not.toBeVisible({ timeout: 10000 });

  await page.getByRole("button", { name: "Log out" }).click();

  // Contributor questionnaire screenshot.
  await loginAsApi(
    page,
    CONTRIBUTOR_EMAIL,
    ADMIN_TOTP.replace(encodeURIComponent(ADMIN_EMAIL), encodeURIComponent(CONTRIBUTOR_EMAIL)),
  );
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  await page.getByRole("link", { name: "My domains" }).click();
  await page.locator(`[data-domain-code="${CODE}"]`).click();
  await expect(page.getByRole("heading", { name: new RegExp(CODE) })).toBeVisible();
  await page.getByTestId("answer-all").click();
  await expect(page.getByRole("button", { name: "Compile" })).toBeEnabled({ timeout: 20000 });
  await page.screenshot({ path: `${SCREENSHOT_DIR}/questionnaire-page.png`, fullPage: true });

  // Submit for review so reviewer queue has an item.
  await page.getByRole("button", { name: "Compile" }).click();
  await expect(page.getByTestId("compiled-narrative")).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByText("in_review")).toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "Log out" }).click();

  // Reviewer queue screenshot.
  await loginAsApi(
    page,
    REVIEWER_EMAIL,
    ADMIN_TOTP.replace(encodeURIComponent(ADMIN_EMAIL), encodeURIComponent(REVIEWER_EMAIL)),
  );
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  await page.getByRole("link", { name: "Review" }).click();
  await expect(page.getByRole("heading", { name: "Review queue" })).toBeVisible();
  await page.screenshot({ path: `${SCREENSHOT_DIR}/review-page.png`, fullPage: true });
});
