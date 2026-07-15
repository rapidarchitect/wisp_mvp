import { expect, test } from "@playwright/test";

import { apiCallRaw, getToken, getDomainAnswers, listDomains, resetDomain } from "./api";
import { generateTotpCode, API_BASE } from "./helpers";
import { resetAll } from "./fixtures";

test.beforeEach(async ({ request }) => {
  await resetAll(request);
});

async function login(email: string) {
  const response = await fetch(`${API_BASE}/api/v1/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      email,
      password: "UserPass123!",
      totp_code: generateTotpCode(),
    }),
  });
  expect(response.status).toBe(200);
  return ((await response.json()) as { token: string }).token;
}

test("admin assigns contributor and reviewer to a domain (ASSN-01)", async () => {
  const adminToken = await login("admin@demo.example.com");

  const response = await fetch(`${API_BASE}/api/v1/domains/PE/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({
      contributor_email: "contributor@demo.example.com",
      reviewer_email: "reviewer@demo.example.com",
    }),
  });

  expect(response.status).toBe(200);
  const assignment = (await response.json()) as {
    code: string;
    contributor_email: string;
    reviewer_email: string;
  };
  expect(assignment.code).toBe("PE");
  expect(assignment.contributor_email).toBe("contributor@demo.example.com");
  expect(assignment.reviewer_email).toBe("reviewer@demo.example.com");
});

test("one contributor and one reviewer at a time (ASSN-02)", async () => {
  const adminToken = await login("admin@demo.example.com");

  const first = await fetch(`${API_BASE}/api/v1/domains/PE/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({
      contributor_email: "contributor@demo.example.com",
      reviewer_email: "reviewer@demo.example.com",
    }),
  });
  expect(first.status).toBe(200);

  const second = await fetch(`${API_BASE}/api/v1/domains/PE/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({
      contributor_email: "contributor2@demo.example.com",
      reviewer_email: "reviewer2@demo.example.com",
    }),
  });
  expect(second.status).toBe(200);
  const updated = (await second.json()) as {
    contributor_email: string;
    reviewer_email: string;
  };
  expect(updated.contributor_email).toBe("contributor2@demo.example.com");
  expect(updated.reviewer_email).toBe("reviewer2@demo.example.com");
});

test("reassignment preserves existing work (ASSN-03)", async () => {
  const adminToken = await login("admin@demo.example.com");
  await resetDomain("AC");

  // Assign original pair.
  await fetch(`${API_BASE}/api/v1/domains/AC/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({
      contributor_email: "contributor@demo.example.com",
      reviewer_email: "reviewer@demo.example.com",
    }),
  });

  // Contributor answers a question.
  const contributorToken = await getToken("contributor@demo.example.com");
  const progress = (await apiCallRaw("/domains/AC/progress", {
    headers: { Authorization: `Bearer ${contributorToken}` },
  }).then((r) => r.json())) as { questions: { id: number }[] };
  const questionId = progress.questions[0].id;
  await apiCallRaw(`/questions/${questionId}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${contributorToken}` },
    body: JSON.stringify({ value: "yes" }),
  });

  // Reassign to new contributor/reviewer.
  await fetch(`${API_BASE}/api/v1/domains/AC/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({
      contributor_email: "contributor2@demo.example.com",
      reviewer_email: "reviewer2@demo.example.com",
    }),
  });

  // Answers should still be present.
  const answers = await getDomainAnswers("AC");
  expect(answers.length).toBeGreaterThan(0);
  expect(answers[0].value).toBe("yes");
});

test("contributor can list only their assigned domains (ASSN-04)", async () => {
  const adminToken = await login("admin@demo.example.com");
  await fetch(`${API_BASE}/api/v1/domains/PE/assign`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({
      contributor_email: "contributor@demo.example.com",
      reviewer_email: "reviewer@demo.example.com",
    }),
  });

  const contributorToken = await login("contributor@demo.example.com");
  const response = await fetch(`${API_BASE}/api/v1/domains/assigned`, {
    headers: { Authorization: `Bearer ${contributorToken}` },
  });

  expect(response.status).toBe(200);
  const domains = (await response.json()) as { code: string; role: string }[];
  expect(Array.isArray(domains)).toBe(true);
  expect(domains.every((d) => d.role === "contributor")).toBe(true);
  expect(domains.some((d) => d.code === "PE")).toBe(true);
});

test("admin can view unassigned domains and non-admin cannot (ASSN-05)", async () => {
  const adminToken = await login("admin@demo.example.com");

  const unassignedResponse = await fetch(`${API_BASE}/api/v1/domains/unassigned`, {
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  expect(unassignedResponse.status).toBe(200);
  const unassigned = (await unassignedResponse.json()) as { code: string }[];
  expect(Array.isArray(unassigned)).toBe(true);

  const contributorToken = await login("contributor@demo.example.com");
  const forbiddenResponse = await fetch(`${API_BASE}/api/v1/domains/unassigned`, {
    headers: { Authorization: `Bearer ${contributorToken}` },
  });
  expect(forbiddenResponse.status).toBe(403);
});
