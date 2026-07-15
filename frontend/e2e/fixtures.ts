import { test as base, expect, Page, APIRequestContext } from "@playwright/test";

import { loginAsApi } from "./api";
import { generateTotpCodeFromUri } from "./helpers";

export const TOTP_URIS: Record<string, string> = {
  "admin@demo.example.com":
    "otpauth://totp/WISPGen:admin%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
  "contributor@demo.example.com":
    "otpauth://totp/WISPGen:contributor%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
  "reviewer@demo.example.com":
    "otpauth://totp/WISPGen:reviewer%40demo.example.com?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
};

export type E2EFixtures = {
  loginAs: (email: string) => Promise<void>;
  api: APIRequestContext;
};

export const test = base.extend<E2EFixtures>({
  loginAs: async ({ page }, use) => {
    await use(async (email: string) => {
      const uri = TOTP_URIS[email];
      if (!uri) throw new Error(`No TOTP URI configured for ${email}`);
      await loginAsApi(page, email, uri);
      await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({
        timeout: 10000,
      });
    });
  },
});

export async function resetAll(request: APIRequestContext): Promise<void> {
  const resp = await request.post("http://demo.localhost:8000/api/v1/test/reset-all", {
    headers: { "X-Test-Mode": "1" },
  });
  expect(resp.ok()).toBeTruthy();
}

export async function loginAs(page: Page, email: string): Promise<void> {
  const uri = TOTP_URIS[email];
  if (!uri) throw new Error(`No TOTP URI configured for ${email}`);
  await loginAsApi(page, email, uri);
  await expect(page.getByRole("heading", { name: "Dashboard" })).toBeVisible({
    timeout: 10000,
  });
}

export function generateTotp(email: string): string {
  return generateTotpCodeFromUri(TOTP_URIS[email]);
}
