import { expect, Page, test } from "@playwright/test";

import { loginAsApi } from "./api";
import { generateTotpCodeFromUri } from "./helpers";

const CONTRIBUTOR_EMAIL = "contributor@demo.example.com";
const REVIEWER_EMAIL = "reviewer@demo.example.com";
const CODE = "AC";

const TOTP_URIS: Record<string, string> = {
  [CONTRIBUTOR_EMAIL]: "otpauth://totp/WISPGen:contributor%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
  [REVIEWER_EMAIL]: "otpauth://totp/WISPGen:reviewer%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
};

async function loginAs(page: Page, email: string) {
  await loginAsApi(page, email, TOTP_URIS[email]);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
}

test.beforeEach(async ({ request }) => {
  const resp = await request.post(`http://demo.localhost:8000/api/v1/test/reset-domain/${CODE}`, {
    headers: { "X-Test-Mode": "1" },
  });
  expect(resp.ok()).toBeTruthy();
});

async function submitDomainForReview(page: Page, code: string) {
  await loginAs(page, CONTRIBUTOR_EMAIL);
  await page.getByRole("link", { name: "My domains" }).click();
  await page.locator(`[data-domain-code="${code}"]`).click();
  await expect(page.getByRole("heading", { name: new RegExp(code) })).toBeVisible();

  const answerAllButton = page.getByTestId("answer-all");
  await expect(answerAllButton).toBeVisible();
  await answerAllButton.click();
  await expect(page.getByRole("button", { name: "Compile" })).toBeEnabled({ timeout: 20000 });

  await page.getByRole("button", { name: "Compile" }).click();
  await expect(page.getByTestId("compiled-narrative")).toBeVisible({ timeout: 20000 });
  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByText("in_review")).toBeVisible({ timeout: 10000 });
}

test("reviewer approves a submitted domain (REVW-01)", async ({ page }) => {
  await submitDomainForReview(page, CODE);

  await page.getByRole("button", { name: "Log out" }).click();
  await loginAs(page, REVIEWER_EMAIL);
  await page.getByRole("link", { name: "Review" }).click();
  await page.locator(`[data-domain-code="${CODE}"]`).click();
  await expect(page.getByRole("heading", { name: new RegExp(`Review .*${CODE}`) })).toBeVisible();

  await page.getByRole("button", { name: "Approve", exact: true }).first().click();
  await expect(page.getByText("Domain approved.")).toBeVisible({ timeout: 10000 });
});

test("reviewer revises with AI and approves (REVW-02)", async ({ page }) => {
  await submitDomainForReview(page, CODE);

  await page.getByRole("button", { name: "Log out" }).click();
  await loginAs(page, REVIEWER_EMAIL);
  await page.getByRole("link", { name: "Review" }).click();
  await page.locator(`[data-domain-code="${CODE}"]`).click();
  await expect(page.getByRole("heading", { name: new RegExp(`Review .*${CODE}`) })).toBeVisible();

  await page.getByLabel("Revision prompt").fill("Add more detail on access logs");
  await page.getByRole("button", { name: "Revise and approve" }).click();
  await expect(page.getByText("Domain revised and approved.")).toBeVisible({ timeout: 10000 });
});
