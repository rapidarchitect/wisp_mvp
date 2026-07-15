import { expect, Page, test } from "@playwright/test";

import { loginAsApi } from "./api";

const CONTRIBUTOR_EMAIL = "contributor@demo.example.com";
const TOTP_URI = "otpauth://totp/WISPGen:contributor%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen";
const CODE = "AC";

async function loginAsContributor(page: Page) {
  await loginAsApi(page, CONTRIBUTOR_EMAIL, TOTP_URI);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
}

test.beforeEach(async ({ request }) => {
  const resp = await request.post(`http://demo.localhost:8000/api/v1/test/reset-domain/${CODE}`, {
    headers: { "X-Test-Mode": "1" },
  });
  expect(resp.ok()).toBeTruthy();
});

test("answering a question generates follow-ups and AI compiles the domain (QSTN-01, QSTN-02)", async ({ page }) => {
  await loginAsContributor(page);

  await page.getByRole("link", { name: "My domains" }).click();
  await expect(page.getByRole("heading", { name: "My domains" })).toBeVisible();
  await page.getByText("Access Control (AC)").click();

  await expect(page.getByRole("heading", { name: /Access Control/ })).toBeVisible();

  // Answer the first question with "yes" to trigger follow-ups from the fake LLM.
  const firstQuestionCard = page.locator(".MuiCard-root[data-question]").filter({ hasText: /1\. Do you restrict physical access/ }).first();
  await expect(firstQuestionCard.getByText(/1\. Do you restrict physical access/)).toBeVisible();
  const yesLabel = page.locator("span[data-choice='yes']").first();
  await expect(yesLabel).toBeVisible();
  await yesLabel.click();

  // Wait for follow-up state to render and assert fake follow-up text appears.
  await expect(firstQuestionCard.getByText(/Follow-ups:/)).toBeVisible({ timeout: 10000 });
  await expect(firstQuestionCard.getByText("fake-llm-response")).toBeVisible();

  // Fill the follow-up response for the first follow-up and let onBlur persist it.
  const firstFollowup = firstQuestionCard.locator("[data-followup]").first();
  const responseInput = firstFollowup.locator("input");
  await responseInput.fill("Documented in policy.");
  await responseInput.blur();
  await page.waitForTimeout(500);

  // Use the answer-all helper to complete any remaining questions and follow-ups.
  const answerAllButton = page.getByTestId("answer-all");
  await expect(answerAllButton).toBeVisible();
  await answerAllButton.click();
  await expect(page.getByRole("button", { name: "Compile" })).toBeEnabled({ timeout: 20000 });

  // Compile the domain.
  await page.getByRole("button", { name: "Compile" }).click();
  await expect(page.getByTestId("compiled-narrative")).toBeVisible({ timeout: 20000 });
  await expect(page.getByTestId("compiled-narrative")).toContainText("fake-llm-response");

  // Submit for review.
  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByText("in_review")).toBeVisible({ timeout: 10000 });
});
