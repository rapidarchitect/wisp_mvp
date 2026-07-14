import { expect, test } from "@playwright/test";

import { apiCall } from "./api";
import { generateTotpCode, generateTotpCodeFromUri } from "./helpers";

test("first login requires TOTP enrollment (AUTH-01)", async ({ page }) => {
  const email = `e2eenroll-${Date.now()}@demo.example.com`;
  await apiCall("/test/users", {
    method: "POST",
    body: JSON.stringify({ email, password: "E2EEnroll123!", totp_enrolled: false }),
  });

  await page.goto("http://demo.localhost:5173/login");
  await expect(page.getByText("Log in to")).toBeVisible();
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password").fill("E2EEnroll123!");
  await page.getByRole("button", { name: "Continue" }).click();
  await expect(page.getByText("Set up two-factor authentication")).toBeVisible({ timeout: 10000 });

  const uri = await page.evaluate(() => localStorage.getItem("wispgen_pending_uri") || "");
  expect(uri).toContain("otpauth://");

  const code = generateTotpCodeFromUri(uri);
  await page.getByRole("textbox", { name: "Authenticator code" }).fill(code);
  await page.getByRole("button", { name: "Verify" }).click();

  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
});

test("login with password and TOTP (AUTH-02)", async ({ page }) => {
  await page.goto("http://demo.localhost:5173/login");
  await expect(page.getByText("Log in to")).toBeVisible();
  await page.getByLabel("Email").fill("admin@demo.example.com");
  await page.getByLabel("Password").fill("UserPass123!");
  await page.getByRole("button", { name: "Continue" }).click();

  await expect(page.getByText("Two-factor authentication")).toBeVisible({ timeout: 10000 });

  const code = generateTotpCode();
  await page.getByLabel("Authenticator code").fill(code);
  await page.getByRole("button", { name: "Verify" }).click();

  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({ timeout: 10000 });
  await expect(page.getByText("Welcome")).toContainText("admin@demo.example.com");
});
