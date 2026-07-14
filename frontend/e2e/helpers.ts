import { TOTP, URI } from "otpauth";

// Fixed secret used by the e2e setup script when seeding test users.
export const TOTP_SECRET = "JBSWY3DPEHPK3PXP";

export function generateTotpCode(secret: string = TOTP_SECRET): string {
  const totp = new TOTP({ secret });
  return totp.generate();
}

export function generateTotpCodeFromUri(uri: string): string {
  const parsed = URI.parse(uri) as TOTP;
  return parsed.generate();
}

export const API_BASE = "http://demo.localhost:8000";
