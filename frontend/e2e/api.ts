import { Page } from "@playwright/test";

import { API_BASE, generateTotpCode, generateTotpCodeFromUri } from "./helpers";

export async function apiCall(path: string, options: RequestInit = {}): Promise<unknown> {
  const response = await fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
  if (!response.ok) {
    throw new Error(`API call failed: ${response.status} ${await response.text()}`);
  }
  if (response.status === 204) return undefined;
  return response.json();
}

export async function apiCallRaw(path: string, options: RequestInit = {}): Promise<Response> {
  return fetch(`${API_BASE}/api/v1${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });
}

export async function loginDemoAdmin(): Promise<{ token: string }> {
  const result = await apiCall("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email: "admin@demo.example.com",
      password: "UserPass123!",
      totp_code: generateTotpCode(),
    }),
  });
  return result as { token: string };
}

export async function loginAsApi(page: Page, email: string, totpUri: string): Promise<void> {
  const totp = generateTotpCodeFromUri(totpUri);
  const result = await apiCall("/auth/login", {
    method: "POST",
    body: JSON.stringify({ email, password: "UserPass123!", totp_code: totp }),
  });
  const data = result as { token: string };
  await page.goto("http://demo.localhost:5173/login");
  await page.evaluate((token: string) => {
    localStorage.setItem("wispgen_token", token);
  }, data.token);
  await page.goto("http://demo.localhost:5173/");
}

export async function testLogin(email: string): Promise<string> {
  const result = await apiCall("/test/login", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
  return (result as { token: string }).token;
}

export async function getToken(email: string): Promise<string> {
  const result = await apiCall("/auth/login", {
    method: "POST",
    body: JSON.stringify({
      email,
      password: "UserPass123!",
      totp_code: generateTotpCodeFromUri(
        "otpauth://totp/WISPGen:" + encodeURIComponent(email) + "?secret=JBSWY3DPEHPK3PXP&issuer=WISPGen",
      ),
    }),
  });
  return (result as { token: string }).token;
}

export async function createTestUser(
  email: string,
  roles: string[] = ["contributor"],
  options: { password?: string; totpEnrolled?: boolean; totpSecret?: string } = {},
): Promise<void> {
  await apiCall("/test/users", {
    method: "POST",
    body: JSON.stringify({
      email,
      password: options.password ?? "UserPass123!",
      roles: JSON.stringify(roles),
      totp_enrolled: options.totpEnrolled ?? true,
      totp_secret: options.totpSecret ?? "JBSWY3DPEHPK3PXP",
    }),
  });
}

export async function inviteUser(token: string, email: string, roles: string[]): Promise<void> {
  const response = await apiCall("/users/invite", {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ email, roles: roles.join(",") }),
  });
  if (!response || typeof response !== "object" || !("token" in response)) {
    throw new Error("Invitation did not return a token");
  }
}

export async function listInvitations(email?: string): Promise<Array<{ token: string; expires_at: string; accepted_at: string | null }>> {
  const path = email ? `/test/invitations?email=${encodeURIComponent(email)}` : "/test/invitations";
  return (await apiCall(path)) as Array<{ token: string; expires_at: string; accepted_at: string | null }>;
}

export async function setStripeMode(mode: "succeed" | "decline"): Promise<void> {
  await apiCall("/test/stripe-mode", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export async function setLlmMode(mode: "normal" | "fail"): Promise<void> {
  await apiCall("/test/llm-mode", {
    method: "POST",
    body: JSON.stringify({ mode }),
  });
}

export async function getSentEmails(email: string): Promise<Array<{ to: string; subject: string; body: string }>> {
  return (await apiCall(`/test/sent-emails?email=${encodeURIComponent(email)}`)) as Array<{
    to: string;
    subject: string;
    body: string;
  }>;
}

export async function getResetToken(email: string): Promise<string | null> {
  const messages = await getSentEmails(email);
  const resetMessage = messages
    .reverse()
    .find((m) => m.subject.toLowerCase().includes("password reset"));
  if (!resetMessage) return null;
  const match = resetMessage.body.match(/token=([^\s]+)/);
  return match?.[1] ?? null;
}

export async function expireInvitation(email: string): Promise<void> {
  await apiCall("/test/expire-invitation", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function expireSessions(email: string): Promise<void> {
  await apiCall("/test/expire-sessions", {
    method: "POST",
    body: JSON.stringify({ email }),
  });
}

export async function deactivateUser(token: string, userId: number): Promise<void> {
  await apiCall(`/users/${userId}/deactivate`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
  });
}

export async function setUserRoles(token: string, userId: number, roles: string[]): Promise<void> {
  await apiCall(`/users/${userId}/roles`, {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    body: JSON.stringify({ roles: roles.join(",") }),
  });
}

export async function listUsers(token: string): Promise<Array<{ id: number; email: string; roles: string[]; status: string }>> {
  return (await apiCall("/users", {
    headers: { Authorization: `Bearer ${token}` },
  })) as Array<{ id: number; email: string; roles: string[]; status: string }>;
}

export async function getDomainAnswers(code: string): Promise<Array<{ id: number; value: string; skipped: number; position: number }>> {
  return (await apiCall(`/test/domain-answers/${code}`)) as Array<{ id: number; value: string; skipped: number; position: number }>;
}

export async function seedDomain(code: string, fail = false): Promise<unknown> {
  return apiCall(`/test/seed-domain/${code}`, {
    method: "POST",
    body: JSON.stringify({ fail }),
  });
}

export async function listDomainQuestions(code: string): Promise<Array<{ id: number; text: string; origin: string; enabled: number; position: number }>> {
  return (await apiCall(`/test/questions/${code}`)) as Array<{ id: number; text: string; origin: string; enabled: number; position: number }>;
}

export async function resetDomain(code: string): Promise<void> {
  await apiCall(`/test/reset-domain/${code}`, {
    method: "POST",
  });
}

export async function listDomains(): Promise<Array<{ code: string; status: string }>> {
  return (await apiCall("/test/domains")) as Array<{ code: string; status: string }>;
}
