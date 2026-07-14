import { API_BASE, generateTotpCode } from "./helpers";

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

