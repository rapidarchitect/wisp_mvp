import { expect, test } from "@playwright/test";

import { loginDemoAdmin } from "./api";
import { generateTotpCodeFromUri } from "./helpers";

const ADMIN_EMAIL = "admin@demo.example.com";
const ADMIN_PASSWORD = "UserPass123!";

test("invited user activates account (USER-02)", async ({ page }) => {
  // Log in as admin to invite a new user.
  await page.goto("http://demo.localhost:5173/login");
  await expect(page.getByText("Log in to")).toBeVisible();
  await page.getByLabel("Email").fill(ADMIN_EMAIL);
  await page.getByLabel("Password").fill(ADMIN_PASSWORD);
  await page.getByRole("button", { name: "Continue" }).click();

  await page.getByLabel("Authenticator code").fill(generateTotpCodeFromUri("otpauth://totp/WISPGen:admin%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen"));
  await page.getByRole("button", { name: "Verify" }).click();
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });

  // Navigate to Users page.
  await page.getByRole("link", { name: "Users" }).click();
  await expect(page.getByRole("heading", { name: "Users and invitations" })).toBeVisible();

  const invitedEmail = `e2eactivate-${Date.now()}@demo.example.com`;
  await page.getByLabel("Email").fill(invitedEmail);
  await page.getByLabel("Roles").click();
  await page.getByRole("option", { name: "admin" }).click();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Send invitation" }).click();

  // Extract token via test-only endpoint.
  const { token } = await loginDemoAdmin();
  const invitations = (await fetch(`http://demo.localhost:8000/api/v1/test/invitations?email=${encodeURIComponent(invitedEmail)}`, {
    headers: { Authorization: `Bearer ${token}` },
  }).then((r) => r.json())) as { token: string }[];
  expect(invitations).toHaveLength(1);
  const activationToken = invitations[0].token;

  // Activate the invited user.
  const activationSecret = "JBSWY3DPEHPK3PXPACTIVATE";
  await page.goto(`http://demo.localhost:5173/activate?token=${activationToken}`);
  await page.getByLabel("Password").fill("NewUserPass123!");
  const activationCode = generateTotpCodeFromUri(`otpauth://totp/WISPGen?secret=${activationSecret}&issuer=WISPGen`);
  await page.getByLabel("Authenticator code").fill(activationCode);
  await page.getByRole("button", { name: "Activate" }).click();

  await expect(page.getByRole("heading", { name: "Log in" })).toBeVisible({ timeout: 10000 });
});
