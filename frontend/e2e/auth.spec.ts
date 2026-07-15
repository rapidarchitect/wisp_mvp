import { expect, test } from "@playwright/test";

import { apiCallRaw, createTestUser, expireSessions, getResetToken, getToken, loginDemoAdmin } from "./api";
import { generateTotpCode, generateTotpCodeFromUri } from "./helpers";
import { resetAll } from "./fixtures";

const ADMIN_EMAIL = "admin@demo.example.com";
const CONTRIBUTOR_EMAIL = "contributor@demo.example.com";
const TOTP_URI = "otpauth://totp/WISPGen:contributor%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen";

async function apiLogin(email: string, password: string, totpCode: string | null = null): Promise<Response> {
  return apiCallRaw("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password,
      totp_code: totpCode,
    }),
  });
}

test.beforeEach(async ({ request }) => {
  await resetAll(request);
});

test("first login requires TOTP enrollment (AUTH-01)", async ({ page }) => {
  const email = `e2eenroll-${Date.now()}@demo.example.com`;
  await createTestUser(email, ["admin"], { totpEnrolled: false });

  await page.goto("http://demo.localhost:5173/login");
  await expect(page.getByText("Log in to")).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("UserPass123!");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Set up two-factor authentication")).toBeVisible({ timeout: 10000 });

  const uri = await page.evaluate(() => localStorage.getItem("wispgen_pending_uri") || "");
  expect(uri).toContain("otpauth://");

  const code = generateTotpCodeFromUri(uri);
  await page.getByRole("textbox", { name: "Authenticator code" }).fill(code);
  await page.getByRole("button", { name: "Verify" }).click();

  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

test("login with password and TOTP (AUTH-02)", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto("http://demo.localhost:5173/login");
  await expect(page.getByText("Log in to")).toBeVisible();
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill("UserPass123!");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByText("Two-factor authentication")).toBeVisible({ timeout: 10000 });

  const code = generateTotpCode();
  await page.getByLabel("Authenticator code").fill(code);
  await page.getByRole("button", { name: "Verify" }).click();

  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("Welcome")).toContainText(ADMIN_EMAIL);
  await context.close();
});

test("wrong password rejected (AUTH-03)", async ({ browser }) => {
  const context = await browser.newContext();
  const page = await context.newPage();

  await page.goto("http://demo.localhost:5173/login");
  await expect(page.getByText("Log in to")).toBeVisible();

  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill("WrongPassword123!");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByText("Invalid email or password")).toBeVisible({ timeout: 10000 });
  await context.close();
});

test("wrong TOTP counts toward lockout but one failure does not lock (AUTH-04)", async () => {
  const email = `e2etotp-${Date.now()}@demo.example.com`;
  await createTestUser(email, ["contributor"]);

  const wrong = await apiLogin(email, "UserPass123!", "000000");
  expect(wrong.status).toBe(401);

  const correct = await apiLogin(email, "UserPass123!", generateTotpCode());
  expect(correct.status).toBe(200);
});

test("lock after 5 failed TOTP attempts (AUTH-05)", async () => {
  const email = `e2elock-${Date.now()}@demo.example.com`;
  await createTestUser(email, ["contributor"]);

  for (let i = 0; i < 5; i += 1) {
    const response = await apiLogin(email, "UserPass123!", "000000");
    expect(response.status).toBe(401);
  }

  const locked = await apiLogin(email, "UserPass123!", generateTotpCode());
  expect(locked.status).toBe(401);
  const body = (await locked.json()) as { error?: { code?: string } };
  expect(body.error?.code).toBe("account_locked");
});

test("expired session preserves saved work (AUTH-06)", async () => {
  const token = await getToken(CONTRIBUTOR_EMAIL);

  // Fetch AC domain progress to discover a question id.
  const progressResponse = await fetch("http://demo.localhost:8000/api/v1/domains/AC/progress", {
    headers: { Authorization: `Bearer ${token}` },
  });
  expect(progressResponse.ok).toBeTruthy();
  const progress = (await progressResponse.json()) as { questions: { id: number }[] };
  expect(progress.questions.length).toBeGreaterThan(0);
  const questionId = progress.questions[0].id;

  // Save an answer.
  const answerResponse = await fetch(`http://demo.localhost:8000/api/v1/questions/${questionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ value: "yes" }),
  });
  expect(answerResponse.ok).toBeTruthy();

  // Simulate session expiry.
  await expireSessions(CONTRIBUTOR_EMAIL);

  // Log in again and verify the answer is still present.
  const newToken = await getToken(CONTRIBUTOR_EMAIL);
  const freshProgressResponse = await fetch("http://demo.localhost:8000/api/v1/domains/AC/progress", {
    headers: { Authorization: `Bearer ${newToken}` },
  });
  expect(freshProgressResponse.ok).toBeTruthy();
  const freshProgress = (await freshProgressResponse.json()) as typeof progress;
  const answered = freshProgress.questions.find((q) => q.id === questionId);
  expect(answered).toBeTruthy();
});

test("password reset via 30-min link (AUTH-07)", async () => {
  const email = `e2ereset-${Date.now()}@demo.example.com`;
  await createTestUser(email, ["admin"]);

  // Request a reset link.
  const requestResponse = await apiCallRaw("/auth/password-reset-request", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
  expect(requestResponse.ok).toBeTruthy();

  // Extract the token from the test-only endpoint.
  const token = await getResetToken(email);
  expect(token).toBeTruthy();

  // Confirm the reset with a new password.
  const newPassword = "ResetPass1234!";
  const confirmResponse = await apiCallRaw("/auth/password-reset", {
    method: "POST",
    body: JSON.stringify({ token, new_password: newPassword }),
  });
  expect(confirmResponse.ok).toBeTruthy();

  // Log in with the new password.
  const loginResponse = await apiLogin(email, newPassword, generateTotpCode());
  expect(loginResponse.status).toBe(200);
  const body = (await loginResponse.json()) as { token: string };
  expect(body.token).toBeTruthy();
});
