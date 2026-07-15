import { expect, Page, test } from "@playwright/test";

import { loginAsApi } from "./api";
import { generateTotpCodeFromUri } from "./helpers";

const ADMIN_EMAIL = "admin@demo.example.com";
const CONTRIBUTOR_EMAIL = "contributor@demo.example.com";
const REVIEWER_EMAIL = "reviewer@demo.example.com";

const TOTP_URIS: Record<string, string> = {
  [ADMIN_EMAIL]: "otpauth://totp/WISPGen:admin%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
  [CONTRIBUTOR_EMAIL]: "otpauth://totp/WISPGen:contributor%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
  [REVIEWER_EMAIL]: "otpauth://totp/WISPGen:reviewer%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
};

async function loginAs(page: Page, email: string) {
  await loginAsApi(page, email, TOTP_URIS[email]);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
}

async function getToken(email: string): Promise<string> {
  const response = await fetch("http://demo.localhost:8000/api/v1/auth/login", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password: "UserPass123!",
      totp_code: generateTotpCodeFromUri(TOTP_URIS[email]),
    }),
  });
  const data = (await response.json()) as { token: string };
  return data.token;
}

async function resetDomain(code: string) {
  const response = await fetch(`http://demo.localhost:8000/api/v1/test/reset-domain/${code}`, {
    method: "POST",
    headers: { "X-Test-Mode": "1" },
  });
  expect(response.ok).toBeTruthy();
}

async function listCurrentVersionDomains(): Promise<{ code: string; status: string }[]> {
  const response = await fetch("http://demo.localhost:8000/api/v1/test/domains", {
    headers: { "X-Test-Mode": "1" },
  });
  return (await response.json()) as { code: string; status: string }[];
}

async function assignDomain(token: string, code: string) {
  const response = await fetch(`http://demo.localhost:8000/api/v1/domains/${code}/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({
      contributor_email: CONTRIBUTOR_EMAIL,
      reviewer_email: REVIEWER_EMAIL,
    }),
  });
  expect(response.ok).toBeTruthy();
}

async function submitAndApproveDomain(code: string) {
  const contributorToken = await getToken(CONTRIBUTOR_EMAIL);

  const progressResponse = await fetch(`http://demo.localhost:8000/api/v1/domains/${code}/progress`, {
    headers: { Authorization: `Bearer ${contributorToken}` },
  });
  expect(progressResponse.ok).toBeTruthy();
  const progress = (await progressResponse.json()) as {
    questions: {
      id: number;
      answer: { followups: { id: number; response_text: string | null }[] } | null;
    }[];
  };

  for (const question of progress.questions) {
    const answerResponse = await fetch(`http://demo.localhost:8000/api/v1/questions/${question.id}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${contributorToken}` },
      body: JSON.stringify({ value: "yes" }),
    });
    expect(answerResponse.ok).toBeTruthy();
  }

  const freshProgressResponse = await fetch(`http://demo.localhost:8000/api/v1/domains/${code}/progress`, {
    headers: { Authorization: `Bearer ${contributorToken}` },
  });
  expect(freshProgressResponse.ok).toBeTruthy();
  const freshProgress = (await freshProgressResponse.json()) as typeof progress;

  for (const question of freshProgress.questions) {
    if (question.answer?.followups) {
      for (const followup of question.answer.followups) {
        if (!followup.response_text) {
          const followupResponse = await fetch(`http://demo.localhost:8000/api/v1/followups/${followup.id}/respond`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${contributorToken}` },
            body: JSON.stringify({ response_text: "Documented in policy." }),
          });
          expect(followupResponse.ok).toBeTruthy();
        }
      }
    }
  }

  const compileResponse = await fetch(`http://demo.localhost:8000/api/v1/domains/${code}/compile`, {
    method: "POST",
    headers: { Authorization: `Bearer ${contributorToken}` },
  });
  expect(compileResponse.ok).toBeTruthy();

  const submitResponse = await fetch(`http://demo.localhost:8000/api/v1/domains/${code}/submit`, {
    method: "POST",
    headers: { Authorization: `Bearer ${contributorToken}` },
  });
  expect(submitResponse.ok).toBeTruthy();

  const reviewerToken = await getToken(REVIEWER_EMAIL);

  const approveResponse = await fetch(`http://demo.localhost:8000/api/v1/domains/${code}/approve`, {
    method: "POST",
    headers: { Authorization: `Bearer ${reviewerToken}` },
  });
  expect(approveResponse.ok).toBeTruthy();
}

async function approveAllDomains() {
  const adminToken = await getToken(ADMIN_EMAIL);
  const domains = await listCurrentVersionDomains();
  for (const domain of domains) {
    await resetDomain(domain.code);
    await assignDomain(adminToken, domain.code);
    await submitAndApproveDomain(domain.code);
  }
}

test.beforeEach(async ({ request }) => {
  const resp = await request.post("http://demo.localhost:8000/api/v1/test/reset-all", {
    headers: { "X-Test-Mode": "1" },
  });
  expect(resp.ok()).toBeTruthy();
});

test("draft export downloads PDF (VERS-01)", async ({ page }) => {
  await loginAs(page, ADMIN_EMAIL);
  await page.getByRole("link", { name: "Versions" }).click();
  await expect(page.getByRole("heading", { name: "Versions and export" })).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Export current version" }).click(),
  ]);

  expect(download.suggestedFilename()).toMatch(/wisp-v\d+-in_progress\.pdf/);
});

test("complete WISP exports clean PDF (VERS-02)", async ({ page }) => {
  await approveAllDomains();

  await loginAs(page, ADMIN_EMAIL);
  await page.getByRole("link", { name: "Versions" }).click();
  await expect(page.getByRole("heading", { name: "Versions and export" })).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Export current version" }).click(),
  ]);

  expect(download.suggestedFilename()).toMatch(/wisp-v\d+-complete\.pdf/);
});

test("new version clones approved baseline (VERS-03)", async ({ page }) => {
  await approveAllDomains();

  await loginAs(page, ADMIN_EMAIL);
  await page.getByRole("link", { name: "Versions" }).click();
  await expect(page.getByRole("heading", { name: "Versions and export" })).toBeVisible();

  await page.getByRole("button", { name: "Start new version" }).click();
  await expect(page.getByText("New version started.")).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("Version 2")).toBeVisible();

  // The latest version should contain all 14 cloned domains.
  const domains = await listCurrentVersionDomains();
  expect(domains.length).toBe(14);
});

test("only one version can be in progress (VERS-04)", async ({ page }) => {
  await approveAllDomains();

  await loginAs(page, ADMIN_EMAIL);
  await page.getByRole("link", { name: "Versions" }).click();
  await page.getByRole("button", { name: "Start new version" }).click();
  await expect(page.getByText("New version started.")).toBeVisible({ timeout: 10000 });

  await page.getByRole("button", { name: "Start new version" }).click();
  await expect(page.getByText(/a version is already in progress|version_in_progress/)).toBeVisible({ timeout: 10000 });
});

test("prior versions remain exportable (VERS-05)", async ({ page }) => {
  await approveAllDomains();

  await loginAs(page, ADMIN_EMAIL);
  await page.getByRole("link", { name: "Versions" }).click();
  await page.getByRole("button", { name: "Start new version" }).click();
  await expect(page.getByText("New version started.")).toBeVisible({ timeout: 10000 });

  // Export the prior (complete) version from the list.
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.locator("li", { hasText: "Version 1" }).getByRole("button", { name: "Export" }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/wisp-v1-complete\.pdf/);
});
