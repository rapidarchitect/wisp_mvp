import { expect, Page, test } from "@playwright/test";

import { apiCallRaw, createTestUser, getToken, loginAsApi, testLogin } from "./api";
import { resetAll } from "./fixtures";

const CONTRIBUTOR_EMAIL = "contributor@demo.example.com";
const REVIEWER_EMAIL = "reviewer@demo.example.com";
const CODE = "AC";

const TOTP_URIS: Record<string, string> = {
  [CONTRIBUTOR_EMAIL]: "otpauth://totp/WISPGen:contributor%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
  [REVIEWER_EMAIL]: "otpauth://totp/WISPGen:reviewer%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
  "admin@demo.example.com": "otpauth://totp/WISPGen:admin%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
};

async function loginAs(page: Page, email: string) {
  await loginAsApi(page, email, TOTP_URIS[email]);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
}

test.beforeEach(async ({ request }) => {
  await resetAll(request);
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

test("reviewer defers a submitted domain (REVW-03)", async ({ page }) => {
  await submitDomainForReview(page, CODE);

  await page.getByRole("button", { name: "Log out" }).click();
  await loginAs(page, REVIEWER_EMAIL);
  await page.getByRole("link", { name: "Review" }).click();
  await page.locator(`[data-domain-code="${CODE}"]`).click();

  await page.getByRole("button", { name: "Defer" }).click();
  await expect(page.getByText("Domain deferred back to contributor.")).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("in_progress")).toBeVisible();
});

test("self-review allowed with warning (REVW-04)", async ({ page }) => {
  const hybridEmail = `e2ehybrid-${Date.now()}@demo.example.com`;
  await createTestUser(hybridEmail, ["contributor", "reviewer"]);

  const adminToken = await testLogin("admin@demo.example.com");
  await apiCallRaw("/domains/AC/assign", {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({ contributor_email: hybridEmail, reviewer_email: hybridEmail }),
  });

  const hybridToken = await getToken(hybridEmail);
  const progress = (await apiCallRaw("/domains/AC/progress", {
    headers: { Authorization: `Bearer ${hybridToken}` },
  }).then((r) => r.json())) as { questions: { id: number; answer: { followups: { id: number; response_text: string | null }[] } | null }[] };
  for (const question of progress.questions) {
    const answer = (await apiCallRaw(`/questions/${question.id}/answer`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Authorization: `Bearer ${hybridToken}` },
      body: JSON.stringify({ value: "yes" }),
    }).then((r) => r.json())) as { followups: { id: number; response_text: string | null }[] };
    for (const followup of answer.followups) {
      if (!followup.response_text) {
        await apiCallRaw(`/followups/${followup.id}/respond`, {
          method: "POST",
          headers: { "Content-Type": "application/json", Authorization: `Bearer ${hybridToken}` },
          body: JSON.stringify({ response_text: "Documented in policy." }),
        });
      }
    }
  }
  await apiCallRaw("/domains/AC/compile", {
    method: "POST",
    headers: { Authorization: `Bearer ${hybridToken}` },
  });
  await apiCallRaw("/domains/AC/submit", {
    method: "POST",
    headers: { Authorization: `Bearer ${hybridToken}` },
  });

  await loginAsApi(page, hybridEmail, `otpauth://totp/WISPGen:${encodeURIComponent(hybridEmail)}?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen`);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  await page.getByRole("link", { name: "Review" }).click();
  await page.locator(`[data-domain-code="${CODE}"]`).click();

  await expect(
    page.getByText("You are also the contributor for this domain. Self-review is allowed but flagged."),
  ).toBeVisible({ timeout: 10000 });
  await page.getByRole("button", { name: "Approve", exact: true }).first().click();
  await expect(page.getByText("Domain approved.")).toBeVisible({ timeout: 10000 });
});

test("all approved completes the WISP (REVW-05)", async ({ page }) => {
  // Approve all 14 domains via API so the WISP version becomes complete.
  const adminToken = await testLogin("admin@demo.example.com");
  const domains = (await apiCallRaw("/test/domains").then((r) => r.json())) as { code: string }[];
  const contributorToken = await testLogin(CONTRIBUTOR_EMAIL);
  const reviewerToken = await testLogin(REVIEWER_EMAIL);

  for (const domain of domains) {
    await apiCallRaw(`/test/reset-domain/${domain.code}`, { method: "POST" });
    await apiCallRaw(`/domains/${domain.code}/assign`, {
      method: "POST",
      headers: { Authorization: `Bearer ${adminToken}` },
      body: JSON.stringify({ contributor_email: CONTRIBUTOR_EMAIL, reviewer_email: REVIEWER_EMAIL }),
    });

    const progress = (await apiCallRaw(`/domains/${domain.code}/progress`, {
      headers: { Authorization: `Bearer ${contributorToken}` },
    }).then((r) => r.json())) as { questions: { id: number; answer: { followups: { id: number; response_text: string | null }[] } | null }[] };
    for (const question of progress.questions) {
      const answer = (await apiCallRaw(`/questions/${question.id}/answer`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${contributorToken}` },
        body: JSON.stringify({ value: "yes" }),
      }).then((r) => r.json())) as { followups: { id: number; response_text: string | null }[] };
      for (const followup of answer.followups) {
        if (!followup.response_text) {
          await apiCallRaw(`/followups/${followup.id}/respond`, {
            method: "POST",
            headers: { "Content-Type": "application/json", Authorization: `Bearer ${contributorToken}` },
            body: JSON.stringify({ response_text: "Documented in policy." }),
          });
        }
      }
    }
    await apiCallRaw(`/domains/${domain.code}/compile`, {
      headers: { Authorization: `Bearer ${contributorToken}` },
      method: "POST",
    });
    await apiCallRaw(`/domains/${domain.code}/submit`, {
      headers: { Authorization: `Bearer ${contributorToken}` },
      method: "POST",
    });
    await apiCallRaw(`/domains/${domain.code}/approve`, {
      headers: { Authorization: `Bearer ${reviewerToken}` },
      method: "POST",
    });
  }

  await loginAs(page, "admin@demo.example.com");
  await page.getByRole("link", { name: "Versions" }).click();
  await expect(page.getByRole("heading", { name: "Versions and export" })).toBeVisible();
  await expect(page.getByText("complete")).toBeVisible();

  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.getByRole("button", { name: "Export current version" }).click(),
  ]);
  expect(download.suggestedFilename()).toMatch(/wisp-v\d+-complete\.pdf/);
});
