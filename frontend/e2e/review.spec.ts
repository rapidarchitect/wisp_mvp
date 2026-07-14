import { expect, test } from "@playwright/test";
import { API_BASE, generateTotpCode } from "./helpers";

async function login(
  request: any,
  email: string,
): Promise<{ token: string; status: number }> {
  const response = await request.post(`${API_BASE}/auth/login`, {
    headers: { Host: "demo.localhost:8000" },
    data: {
      email,
      password: "UserPass123!",
      totp_code: generateTotpCode(),
    },
  });
  const status = response.status();
  const body = status === 200 ? await response.json() : {};
  return { token: body.token || "", status };
}

async function assignDomain(
  request: any,
  token: string,
  code: string,
  contributorEmail: string,
  reviewerEmail: string,
) {
  const response = await request.post(`${API_BASE}/domains/${code}/assign`, {
    headers: {
      Host: "demo.localhost:8000",
      Authorization: `Bearer ${token}`,
    },
    data: {
      contributor_email: contributorEmail,
      reviewer_email: reviewerEmail,
    },
  });
  expect(response.status()).toBe(200);
}

async function answerAllQuestions(request: any, token: string, code: string) {
  const progressResponse = await request.get(
    `${API_BASE}/domains/${code}/progress`,
    {
      headers: {
        Host: "demo.localhost:8000",
        Authorization: `Bearer ${token}`,
      },
    },
  );
  expect(progressResponse.status()).toBe(200);
  const progress = await progressResponse.json();

  for (const question of progress.questions) {
    const answerResponse = await request.post(
      `${API_BASE}/questions/${question.id}/answer`,
      {
        headers: {
          Host: "demo.localhost:8000",
          Authorization: `Bearer ${token}`,
        },
        data: { value: "yes" },
      },
    );
    expect(answerResponse.status()).toBe(200);
    const answer = await answerResponse.json();

    for (const followup of answer.followups) {
      const respondResponse = await request.post(
        `${API_BASE}/followups/${followup.id}/respond`,
        {
          headers: {
            Host: "demo.localhost:8000",
            Authorization: `Bearer ${token}`,
          },
          data: { response_text: "Documented in our policy." },
        },
      );
      expect(respondResponse.status()).toBe(200);
    }
  }
}

async function compileAndSubmit(
  request: any,
  token: string,
  code: string,
): Promise<string> {
  const compileResponse = await request.post(
    `${API_BASE}/domains/${code}/compile`,
    {
      headers: {
        Host: "demo.localhost:8000",
        Authorization: `Bearer ${token}`,
      },
    },
  );
  expect(compileResponse.status()).toBe(200);
  const compiled = await compileResponse.json();
  expect(compiled.narrative_text).toBeTruthy();

  const submitResponse = await request.post(
    `${API_BASE}/domains/${code}/submit`,
    {
      headers: {
        Host: "demo.localhost:8000",
        Authorization: `Bearer ${token}`,
      },
    },
  );
  expect(submitResponse.status()).toBe(200);
  const submitted = await submitResponse.json();
  expect(submitted.status).toBe("in_review");
  return submitted.status;
}

test.describe("Review Workflow E2E", () => {
  test("reviewer approves a submitted domain", async ({ request }) => {
    const admin = await login(request, "admin@demo.example.com");
    expect(admin.status).toBe(200);

    const unassignedResponse = await request.get(
      `${API_BASE}/domains/unassigned`,
      {
        headers: {
          Host: "demo.localhost:8000",
          Authorization: `Bearer ${admin.token}`,
        },
      },
    );
    expect(unassignedResponse.status()).toBe(200);
    const unassigned = await unassignedResponse.json();
    expect(unassigned.length).toBeGreaterThan(0);
    const domainCode = unassigned[0].code;

    await assignDomain(
      request,
      admin.token,
      domainCode,
      "contributor@demo.example.com",
      "reviewer@demo.example.com",
    );

    const contributor = await login(request, "contributor@demo.example.com");
    expect(contributor.status).toBe(200);
    await answerAllQuestions(request, contributor.token, domainCode);
    await compileAndSubmit(request, contributor.token, domainCode);

    const reviewer = await login(request, "reviewer@demo.example.com");
    expect(reviewer.status).toBe(200);

    const approveResponse = await request.post(
      `${API_BASE}/domains/${domainCode}/approve`,
      {
        headers: {
          Host: "demo.localhost:8000",
          Authorization: `Bearer ${reviewer.token}`,
        },
      },
    );
    expect(approveResponse.status()).toBe(200);
    const approved = await approveResponse.json();
    expect(approved.status).toBe("approved");
    expect(approved.self_review).toBe(false);
  });
});
