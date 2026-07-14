import { expect, test } from "@playwright/test";
import { API_BASE, generateTotpCode } from "./helpers";

// End-to-end API smoke tests for the contributor questionnaire flow.
// The frontend is still a scaffold; these tests exercise the full backend stack.

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

test.describe("Contributor Questionnaire E2E", () => {
  test("contributor answers a question, responds to follow-ups, and domain becomes submittable", async ({
    request,
  }) => {
    // Admin assigns an unassigned domain to the deterministic contributor/reviewer.
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

    const assignResponse = await request.post(
      `${API_BASE}/domains/${domainCode}/assign`,
      {
        headers: {
          Host: "demo.localhost:8000",
          Authorization: `Bearer ${admin.token}`,
        },
        data: {
          contributor_email: "contributor@demo.example.com",
          reviewer_email: "reviewer@demo.example.com",
        },
      },
    );
    expect(assignResponse.status()).toBe(200);

    // Contributor fetches progress to discover a question id.
    const contributor = await login(request, "contributor@demo.example.com");
    expect(contributor.status).toBe(200);

    const progressResponse = await request.get(
      `${API_BASE}/domains/${domainCode}/progress`,
      {
        headers: {
          Host: "demo.localhost:8000",
          Authorization: `Bearer ${contributor.token}`,
        },
      },
    );
    expect(progressResponse.status()).toBe(200);
    const progress = await progressResponse.json();
    expect(progress.questions.length).toBeGreaterThan(0);
    const question = progress.questions[0];

    // Answer every question in the domain and respond to any generated follow-ups.
    for (const question of progress.questions) {
      const answerResponse = await request.post(
        `${API_BASE}/questions/${question.id}/answer`,
        {
          headers: {
            Host: "demo.localhost:8000",
            Authorization: `Bearer ${contributor.token}`,
          },
          data: { value: "yes" },
        },
      );
      expect(answerResponse.status()).toBe(200);
      const answer = await answerResponse.json();
      expect(answer.value).toBe("yes");
      expect(answer.followups.length).toBeGreaterThanOrEqual(0);
      expect(answer.followups.length).toBeLessThanOrEqual(3);

      for (const followup of answer.followups) {
        const respondResponse = await request.post(
          `${API_BASE}/followups/${followup.id}/respond`,
          {
            headers: {
              Host: "demo.localhost:8000",
              Authorization: `Bearer ${contributor.token}`,
            },
            data: { response_text: "Documented in our policy." },
          },
        );
        expect(respondResponse.status()).toBe(200);
      }
    }

    // Domain should now be ready for submission.
    const finalProgressResponse = await request.get(
      `${API_BASE}/domains/${domainCode}/progress`,
      {
        headers: {
          Host: "demo.localhost:8000",
          Authorization: `Bearer ${contributor.token}`,
        },
      },
    );
    expect(finalProgressResponse.status()).toBe(200);
    const finalProgress = await finalProgressResponse.json();
    expect(finalProgress.submit_ready).toBe(true);
  });
});
