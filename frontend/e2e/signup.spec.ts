import { expect, test } from "@playwright/test";

test("card signup provisions workspace (SIGN-01)", async ({ page }) => {
  const slug = `e2esignup-${Date.now()}`;
  const email = `admin@${slug}.app.wisp.llc`;

  await page.goto(`http://${slug}.localhost:5173/signup`);
  await expect(page.getByText("Create your workspace")).toBeVisible();

  await page.getByLabel("Company name").fill("E2E Signup Firm");
  await page.getByLabel("Address").fill("1 E2E Way");
  await page.getByLabel("Workspace email").fill(email);

  await page.getByRole("radio", { name: "Credit card" }).check();

  await page.getByLabel("Employee range").fill("1-10");
  await page.getByLabel("Clients per year range").fill("100-500");
  await page.getByLabel("Primary software").fill("QuickBooks Online");
  await page.getByLabel("Deployment type").fill("cloud");
  await page.getByLabel("IT support provider").fill("Internal IT");
  await page.getByLabel("Coordinator name").fill("E2E Coordinator");
  await page.getByLabel("Coordinator title").fill("Office Manager");

  await page.getByRole("button", { name: "Create workspace" }).click();
  await expect(page.locator("h4")).toContainText("Payment required", { timeout: 10000 });

  await page.click('[data-testid="test-confirm-card"]');
  await expect(page.locator("h4")).toContainText("Workspace ready", { timeout: 10000 });
  await expect(page.locator("text=Your workspace")).toContainText(slug);
});
