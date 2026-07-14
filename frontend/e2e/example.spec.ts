import { expect, test } from "@playwright/test";

test("homepage loads", async ({ page }) => {
  await page.goto("http://localhost:4173/");
  await expect(page.locator("h1")).toContainText("WISPGen");
});
