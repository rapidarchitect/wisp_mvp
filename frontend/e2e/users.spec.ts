import { expect, test } from "@playwright/test";

import {
  apiCallRaw,
  createTestUser,
  deactivateUser,
  expireInvitation,
  getDomainAnswers,
  getToken,
  inviteUser,
  listDomains,
  listInvitations,
  listUsers,
  loginAsApi,
  setUserRoles,
} from "./api";
import { generateTotpCodeFromUri } from "./helpers";
import { resetAll } from "./fixtures";

const ADMIN_EMAIL = "admin@demo.example.com";
const TOTP_URI = "otpauth://totp/WISPGen:admin%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen";

test.beforeEach(async ({ request }) => {
  await resetAll(request);
});

async function loginAsAdmin(page: any) {
  await loginAsApi(page, ADMIN_EMAIL, TOTP_URI);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
}

test("invite user with two roles (USER-01)", async ({ page }) => {
  await loginAsAdmin(page);

  await page.getByRole("link", { name: "Users" }).click();
  await expect(page.getByRole("heading", { name: "Users and invitations" })).toBeVisible();

  const invitedEmail = `e2einvite-${Date.now()}@demo.example.com`;
  await page.getByLabel("Email").fill(invitedEmail);
  await page.getByRole("combobox", { name: "Roles" }).click();
  await expect(page.getByRole("option", { name: "reviewer" })).toBeVisible();
  await page.getByRole("option", { name: "reviewer" }).click();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Invite" }).click();

  await expect(page.getByRole("heading", { name: "Pending invitations" })).toBeVisible();
  const invitedItem = page.getByTestId(`invitation-${invitedEmail}`);
  await expect(invitedItem).toBeVisible({ timeout: 10000 });
  await expect(invitedItem).toContainText("contributor, reviewer");
});

test("invited user activates account (USER-02)", async ({ page }) => {
  await loginAsAdmin(page);

  await page.getByRole("link", { name: "Users" }).click();
  await expect(page.getByRole("heading", { name: "Users and invitations" })).toBeVisible();

  const invitedEmail = `e2eactivate-${Date.now()}@demo.example.com`;
  await page.getByLabel("Email").fill(invitedEmail);
  await page.getByRole("combobox", { name: "Roles" }).click();
  await expect(page.getByRole("option", { name: "admin" })).toBeVisible();
  // Deselect the default contributor role so only admin remains.
  await page.getByRole("option", { name: "contributor" }).click();
  await page.getByRole("option", { name: "admin" }).click();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Invite" }).click();
  await expect(
    page.getByTestId(`invitation-${invitedEmail}`),
  ).toBeVisible({ timeout: 10000 });

  const invitations = await listInvitations(invitedEmail);
  expect(invitations).toHaveLength(1);
  const activationToken = invitations[0].token;

  const activationSecret = "JBSWY3DPEHPK3PXPACTIVATE";
  await page.goto(`http://demo.localhost:5173/activate?token=${activationToken}`);
  await page.getByLabel("Password").fill("NewUserPass123!");
  const activationCode = generateTotpCodeFromUri(
    `otpauth://totp/WISPGen?secret=${activationSecret}&issuer=WISPGen`,
  );
  await page.getByLabel("Authenticator code").fill(activationCode);
  await page.getByRole("button", { name: "Activate" }).click();

  await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible({ timeout: 10000 });
});

test("one user holds all three roles (USER-03)", async () => {
  const email = `e2eallroles-${Date.now()}@demo.example.com`;
  await createTestUser(email, ["admin", "contributor", "reviewer"]);

  const adminToken = await getToken(ADMIN_EMAIL);
  const users = await listUsers(adminToken);
  const target = users.find((u) => u.email === email);
  expect(target).toBeTruthy();
  expect(target!.roles.sort()).toEqual(["admin", "contributor", "reviewer"]);
});

test("duplicate invitation rejected (USER-04)", async () => {
  const adminToken = await getToken(ADMIN_EMAIL);
  const email = `e2eduplicate-${Date.now()}@demo.example.com`;

  await inviteUser(adminToken, email, ["contributor"]);

  const second = await apiCallRaw("/users/invite", {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({ email, roles: "contributor" }),
  });
  expect(second.status).toBe(409);
});

test("expired invitation link refused (USER-05)", async () => {
  const adminToken = await getToken(ADMIN_EMAIL);
  const email = `e2eexpired-${Date.now()}@demo.example.com`;

  await inviteUser(adminToken, email, ["contributor"]);
  await expireInvitation(email);

  const invitations = await listInvitations(email);
  expect(invitations).toHaveLength(1);
  const token = invitations[0].token;

  const response = await apiCallRaw("/users/accept", {
    method: "POST",
    body: JSON.stringify({
      token,
      password: "UserPass123!",
      totp_secret: "JBSWY3DPEHPK3PXP",
    }),
  });
  expect(response.status).toBe(422);
});

test("admin can reactivate a deactivated user (USER-07)", async ({ page }) => {
  const adminToken = await getToken(ADMIN_EMAIL);
  const email = `e2ereactivate-${Date.now()}@demo.example.com`;
  await createTestUser(email, ["contributor"]);
  const usersBefore = await listUsers(adminToken);
  const target = usersBefore.find((u) => u.email === email);
  expect(target).toBeTruthy();
  await deactivateUser(adminToken, target!.id);

  await loginAsAdmin(page);
  await page.getByRole("link", { name: "Users" }).click();
  const row = page.locator("tr").filter({ hasText: email });
  await expect(row).toContainText("deactivated", { timeout: 10000 });
  await row.getByRole("button", { name: "Reactivate" }).click();
  await expect(row).toContainText("active", { timeout: 10000 });

  const usersAfter = await listUsers(adminToken);
  const reactivated = usersAfter.find((u) => u.email === email);
  expect(reactivated?.status).toBe("active");
});

test("admin can delete a user (USER-08)", async ({ page }) => {
  const adminToken = await getToken(ADMIN_EMAIL);
  const email = `e2edelete-${Date.now()}@demo.example.com`;
  await createTestUser(email, ["contributor"]);

  await loginAsAdmin(page);
  await page.getByRole("link", { name: "Users" }).click();
  const row = page.locator("tr").filter({ hasText: email });
  await expect(row).toBeVisible({ timeout: 10000 });
  await row.getByRole("button", { name: "Delete" }).click();
  await page.locator('[role="dialog"]').getByRole("button", { name: "Delete" }).click();
  await expect(row).not.toBeVisible({ timeout: 10000 });

  const usersAfter = await listUsers(adminToken);
  expect(usersAfter.find((u) => u.email === email)).toBeUndefined();
});

test("deactivation flags domains and keeps answers (USER-06)", async () => {
  const adminToken = await getToken(ADMIN_EMAIL);
  const contributorEmail = `e2edeactivate-${Date.now()}@demo.example.com`;
  await createTestUser(contributorEmail, ["contributor"]);

  // Assign the user to AC as contributor and a reviewer.
  await apiCallRaw("/domains/AC/assign", {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({ contributor_email: contributorEmail, reviewer_email: "reviewer@demo.example.com" }),
  });

  // Answer a question via API.
  const token = await getToken(contributorEmail);
  const progress = (await apiCallRaw("/domains/AC/progress", {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => r.json())) as { questions: { id: number }[] };
  const questionId = progress.questions[0].id;
  await apiCallRaw(`/questions/${questionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ value: "yes" }),
  });

  // Deactivate the user.
  const users = await listUsers(adminToken);
  const target = users.find((u) => u.email === contributorEmail);
  expect(target).toBeTruthy();
  await deactivateUser(adminToken, target!.id);

  // Domain should be flagged as pending_questions and answers preserved.
  const domains = await listDomains();
  const ac = domains.find((d) => d.code === "AC");
  expect(ac?.status).toBe("pending_questions");

  const answers = await getDomainAnswers("AC");
  expect(answers.length).toBeGreaterThan(0);
  expect(answers[0].value).toBe("yes");
});
