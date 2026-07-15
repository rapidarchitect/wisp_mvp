import { expect, test } from "@playwright/test";

import {
  apiCallRaw,
  getToken,
  listDomainQuestions,
  listDomains,
  seedDomain,
} from "./api";
import { resetAll } from "./fixtures";

test.beforeEach(async ({ request }) => {
  await resetAll(request);
});

test("14 domains seeded, 5-10 questions each (SEED-01)", async () => {
  const domains = await listDomains();
  expect(domains.length).toBe(14);

  for (const domain of domains) {
    const questions = await listDomainQuestions(domain.code);
    expect(questions.length).toBeGreaterThanOrEqual(5);
    expect(questions.length).toBeLessThanOrEqual(10);
    expect(questions.every((q) => q.origin === "seeded")).toBe(true);
  }
});

test("demo company after deployment has 14 ready domains (SEED-02)", async () => {
  const domains = await listDomains();
  expect(domains.length).toBe(14);
  const codes = domains.map((d) => d.code).sort();
  expect(codes).toContain("AC");
  expect(codes).toContain("PE");
  expect(codes).toContain("PS");
});

test("research outage degrades a domain to pending_questions (SEED-03)", async () => {
  // Re-seed a domain with the LLM forced to fail.
  const result = (await seedDomain("PE", true)) as {
    status: string;
    seeded: number;
    error?: string;
  };
  expect(result.status).toBe("pending_questions");
  expect(result.seeded).toBe(0);
  expect(result.error).toBeTruthy();

  const domains = await listDomains();
  const pe = domains.find((d) => d.code === "PE");
  expect(pe?.status).toBe("pending_questions");
});

test("admin adds custom question (SEED-04)", async () => {
  const adminToken = await getToken("admin@demo.example.com");
  const peQuestions = await listDomainQuestions("PE");
  const position = Math.max(...peQuestions.map((q) => q.position), 0) + 1;

  const domains = await listDomains();
  const pe = domains.find((d) => d.code === "PE");
  expect(pe).toBeTruthy();
  const peId = (await fetch("http://demo.localhost:8000/api/v1/test/domains", {
    headers: { "X-Test-Mode": "1" },
  }).then((r) => r.json())) as Array<{ code: string; id: number }>;
  const peDomainId = peId.find((d) => d.code === "PE")?.id;
  expect(peDomainId).toBeTruthy();

  const response = await apiCallRaw("/questions", {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({
      domain_id: peDomainId,
      text: "E2E custom question",
      position,
    }),
  });
  expect(response.status).toBe(200);
});

test("admin disables seeded question (SEED-05)", async () => {
  const adminToken = await getToken("admin@demo.example.com");
  const questions = await listDomainQuestions("PE");
  const seeded = questions.find((q) => q.origin === "seeded");
  expect(seeded).toBeTruthy();

  const response = await apiCallRaw(`/questions/${seeded!.id}/disable`, {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  expect(response.status).toBe(200);

  const updated = await listDomainQuestions("PE");
  const disabled = updated.find((q) => q.id === seeded!.id);
  expect(disabled?.enabled).toBe(0);
});

test("regeneration only when unanswered (SEED-06)", async () => {
  const adminToken = await getToken("admin@demo.example.com");

  // Assign PE so the contributor can answer it.
  await apiCallRaw("/domains/PE/assign", {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
    body: JSON.stringify({
      contributor_email: "contributor@demo.example.com",
      reviewer_email: "reviewer@demo.example.com",
    }),
  });

  // Answer a question in PE so regeneration is blocked.
  const contributorToken = await getToken("contributor@demo.example.com");
  const progressResponse = await fetch("http://demo.localhost:8000/api/v1/domains/PE/progress", {
    headers: { Authorization: `Bearer ${contributorToken}` },
  });
  expect(progressResponse.ok).toBeTruthy();
  const progress = (await progressResponse.json()) as { questions: { id: number }[] };
  await fetch(`http://demo.localhost:8000/api/v1/questions/${progress.questions[0].id}/answer`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${contributorToken}` },
    body: JSON.stringify({ value: "yes" }),
  });

  const domains = await fetch("http://demo.localhost:8000/api/v1/test/domains", {
    headers: { "X-Test-Mode": "1" },
  }).then((r) => r.json()) as Array<{ id: number; code: string }>;
  const peId = domains.find((d) => d.code === "PE")!.id;
  const response = await apiCallRaw(`/domains/${peId}/regenerate-questions`, {
    method: "POST",
    headers: { Authorization: `Bearer ${adminToken}` },
  });
  expect(response.status).toBe(409);
});
