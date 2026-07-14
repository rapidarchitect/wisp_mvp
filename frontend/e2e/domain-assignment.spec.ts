import { expect, test } from "@playwright/test";
import { API_BASE, generateTotpCode } from "./helpers";

// End-to-end API smoke tests for the domain assignment feature.
// The frontend is still a scaffold, so these tests exercise the full
// backend stack (HTTP → middleware → services → SQLite) from a client.

test.describe("Domain Assignment E2E", () => {
  test("frontend scaffold loads", async ({ page }) => {
    await page.goto("/");
    await expect(page.locator("h1")).toContainText("WISPGen");
  });

  test("admin can assign contributor and reviewer to a domain", async ({
    request,
  }) => {
    const loginResponse = await request.post(`${API_BASE}/auth/login`, {
      headers: { Host: "demo.localhost:8000" },
      data: {
        email: "admin@demo.example.com",
        password: "UserPass123!",
        totp_code: generateTotpCode(),
      },
    });
    expect(loginResponse.status()).toBe(200);
    const loginBody = await loginResponse.json();
    const token = loginBody.token;

    const assignResponse = await request.post(`${API_BASE}/domains/AC/assign`, {
      headers: {
        Host: "demo.localhost:8000",
        Authorization: `Bearer ${token}`,
      },
      data: {
        contributor_email: "contributor@demo.example.com",
        reviewer_email: "reviewer@demo.example.com",
      },
    });

    expect(assignResponse.status()).toBe(200);
    const assignment = await assignResponse.json();
    expect(assignment.code).toBe("AC");
    expect(assignment.contributor_email).toBe("contributor@demo.example.com");
    expect(assignment.reviewer_email).toBe("reviewer@demo.example.com");
  });

  test("contributor can list only their assigned domains", async ({
    request,
  }) => {
    const loginResponse = await request.post(`${API_BASE}/auth/login`, {
      headers: { Host: "demo.localhost:8000" },
      data: {
        email: "contributor@demo.example.com",
        password: "UserPass123!",
        totp_code: generateTotpCode(),
      },
    });
    expect(loginResponse.status()).toBe(200);
    const token = (await loginResponse.json()).token;

    const assignedResponse = await request.get(`${API_BASE}/domains/assigned`, {
      headers: {
        Host: "demo.localhost:8000",
        Authorization: `Bearer ${token}`,
      },
    });

    expect(assignedResponse.status()).toBe(200);
    const domains = await assignedResponse.json();
    expect(Array.isArray(domains)).toBe(true);
    expect(domains.every((d: any) => d.role === "contributor")).toBe(true);
    expect(domains.some((d: any) => d.code === "AC")).toBe(true);
  });

  test("admin can view unassigned domains", async ({ request }) => {
    const loginResponse = await request.post(`${API_BASE}/auth/login`, {
      headers: { Host: "demo.localhost:8000" },
      data: {
        email: "admin@demo.example.com",
        password: "UserPass123!",
        totp_code: generateTotpCode(),
      },
    });
    expect(loginResponse.status()).toBe(200);
    const token = (await loginResponse.json()).token;

    const unassignedResponse = await request.get(
      `${API_BASE}/domains/unassigned`,
      {
        headers: {
          Host: "demo.localhost:8000",
          Authorization: `Bearer ${token}`,
        },
      },
    );

    expect(unassignedResponse.status()).toBe(200);
    const unassigned = await unassignedResponse.json();
    expect(Array.isArray(unassigned)).toBe(true);
  });

  test("non-admin cannot list unassigned domains", async ({ request }) => {
    const loginResponse = await request.post(`${API_BASE}/auth/login`, {
      headers: { Host: "demo.localhost:8000" },
      data: {
        email: "contributor@demo.example.com",
        password: "UserPass123!",
        totp_code: generateTotpCode(),
      },
    });
    expect(loginResponse.status()).toBe(200);
    const token = (await loginResponse.json()).token;

    const unassignedResponse = await request.get(
      `${API_BASE}/domains/unassigned`,
      {
        headers: {
          Host: "demo.localhost:8000",
          Authorization: `Bearer ${token}`,
        },
      },
    );

    expect(unassignedResponse.status()).toBe(403);
  });

  test("reassignment replaces existing roles", async ({ request }) => {
    const adminLogin = await request.post(`${API_BASE}/auth/login`, {
      headers: { Host: "demo.localhost:8000" },
      data: {
        email: "admin@demo.example.com",
        password: "UserPass123!",
        totp_code: generateTotpCode(),
      },
    });
    expect(adminLogin.status()).toBe(200);
    const adminToken = (await adminLogin.json()).token;

    // First assignment.
    const firstResponse = await request.post(`${API_BASE}/domains/PE/assign`, {
      headers: {
        Host: "demo.localhost:8000",
        Authorization: `Bearer ${adminToken}`,
      },
      data: {
        contributor_email: "contributor@demo.example.com",
        reviewer_email: "reviewer@demo.example.com",
      },
    });
    expect(firstResponse.status()).toBe(200);

    // Reassignment.
    const secondResponse = await request.post(`${API_BASE}/domains/PE/assign`, {
      headers: {
        Host: "demo.localhost:8000",
        Authorization: `Bearer ${adminToken}`,
      },
      data: {
        contributor_email: "contributor2@demo.example.com",
        reviewer_email: "reviewer2@demo.example.com",
      },
    });
    expect(secondResponse.status()).toBe(200);
    const second = await secondResponse.json();
    expect(second.contributor_email).toBe("contributor2@demo.example.com");
    expect(second.reviewer_email).toBe("reviewer2@demo.example.com");
  });
});
