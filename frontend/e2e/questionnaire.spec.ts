import { expect, Page, test } from "@playwright/test";

import { apiCallRaw, loginAsApi, setLlmMode, testLogin } from "./api";
import { resetAll } from "./fixtures";

const CONTRIBUTOR_EMAIL = "contributor@demo.example.com";
const REVIEWER_EMAIL = "reviewer@demo.example.com";
const TOTP_URI = "otpauth://totp/WISPGen:contributor%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen";
const CODE = "AC";

async function loginAsContributor(page: Page) {
  await loginAsApi(page, CONTRIBUTOR_EMAIL, TOTP_URI);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
}

test.beforeEach(async ({ request }) => {
  await resetAll(request);
});

test("answering a question generates follow-ups and AI compiles the domain (QSTN-01, QSTN-02)", async ({ page }) => {
  await loginAsContributor(page);

  await page.getByRole("link", { name: "My domains" }).click();
  await expect(page.getByRole("heading", { name: "My domains" })).toBeVisible();
  await page.getByText("Access Control (AC)").click();

  await expect(page.getByRole("heading", { name: /Access Control/ })).toBeVisible();

  const firstQuestionCard = page.locator(".MuiCard-root[data-question]").filter({ hasText: /1\. Do you restrict physical access/ }).first();
  await expect(firstQuestionCard.getByText(/1\. Do you restrict physical access/)).toBeVisible();
  const yesLabel = page.locator("span[data-choice='yes']").first();
  await expect(yesLabel).toBeVisible();
  await yesLabel.click();

  await expect(firstQuestionCard.getByText(/Follow-ups:/)).toBeVisible({ timeout: 10000 });
  await expect(firstQuestionCard.getByText("fake-llm-response")).toBeVisible();

  const firstFollowup = firstQuestionCard.locator("[data-followup]").first();
  const responseInput = firstFollowup.locator("input");
  await responseInput.fill("Documented in policy.");
  await responseInput.blur();
  await page.waitForTimeout(500);

  const answerAllButton = page.getByTestId("answer-all");
  await expect(answerAllButton).toBeVisible();
  await answerAllButton.click();
  await expect(page.getByRole("button", { name: "Compile" })).toBeEnabled({ timeout: 20000 });

  await page.getByRole("button", { name: "Compile" }).click();
  await expect(page.getByTestId("compiled-narrative")).toBeVisible({ timeout: 20000 });
  await expect(page.getByTestId("compiled-narrative")).toContainText("fake-llm-response");

  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByText("in_review")).toBeVisible({ timeout: 10000 });
});

test("submission sends domain to review (QSTN-03)", async ({ page }) => {
  await loginAsContributor(page);
  await page.getByRole("link", { name: "My domains" }).click();
  await page.locator(`[data-domain-code="${CODE}"]`).click();

  await page.getByTestId("answer-all").click();
  await expect(page.getByRole("button", { name: "Compile" })).toBeEnabled({ timeout: 20000 });
  await page.getByRole("button", { name: "Compile" }).click();
  await expect(page.getByTestId("compiled-narrative")).toBeVisible({ timeout: 20000 });

  await page.getByRole("button", { name: "Submit for review" }).click();
  await expect(page.getByText("in_review")).toBeVisible({ timeout: 10000 });
});

test("skipped question blocks compile and submit (QSTN-04)", async ({ page }) => {
  await loginAsContributor(page);
  await page.getByRole("link", { name: "My domains" }).click();
  await page.locator(`[data-domain-code="${CODE}"]`).click();

  // Skip the first question.
  const firstCard = page.locator(".MuiCard-root[data-question]").first();
  await firstCard.getByRole("button", { name: "Skip" }).click();
  await expect(firstCard.getByText("Skipped")).toBeVisible({ timeout: 10000 });

  // Compile and submit should be disabled.
  await expect(page.getByRole("button", { name: "Compile" })).toBeDisabled();
  await expect(page.getByRole("button", { name: "Submit for review" })).toBeDisabled();
});

test("save and resume exact progress (QSTN-05)", async ({ page }) => {
  await loginAsContributor(page);
  await page.getByRole("link", { name: "My domains" }).click();
  await page.locator(`[data-domain-code="${CODE}"]`).click();

  // Answer the first question.
  const firstCard = page.locator(".MuiCard-root[data-question]").first();
  await firstCard.locator("span[data-choice='yes']").click();
  await expect(firstCard.locator("[data-answered='true']")).toBeVisible({ timeout: 10000 });

  // Navigate away and back.
  await page.getByRole("link", { name: "Dashboard" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible();
  await page.getByRole("link", { name: "My domains" }).click();
  await page.locator(`[data-domain-code="${CODE}"]`).click();

  // The first question should still be answered.
  const resumedCard = page.locator(".MuiCard-root[data-question]").first();
  await expect(resumedCard.locator("[data-answered='true']")).toBeVisible({ timeout: 10000 });
});

test("AI outage falls back to plain answer (QSTN-06)", async () => {
  await setLlmMode("fail");
  const adminToken = await testLogin("admin@demo.example.com");
  await apiCallRaw("/domains/AC/assign", {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({ contributor_email: CONTRIBUTOR_EMAIL, reviewer_email: REVIEWER_EMAIL }),
  });
  const token = await testLogin(CONTRIBUTOR_EMAIL);

  const progress = (await apiCallRaw("/domains/AC/progress", {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => r.json())) as { questions: { id: number }[] };

  const answer = (await apiCallRaw(`/questions/${progress.questions[0].id}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ value: "yes" }),
  }).then((r) => r.json())) as { followups_state: string };

  expect(answer.followups_state).toBe("waived");
  await setLlmMode("normal");
});
