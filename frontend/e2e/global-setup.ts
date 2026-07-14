import { execSync } from "child_process";
import { writeFileSync } from "fs";
import path from "path";
import { fileURLToPath } from "url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const setupScript = path.join(__dirname, "setup.py");

export default async function globalSetup() {
  // Seed the demo tenant and deterministic test users.
  const output = execSync(`cd ../ && uv run python ${setupScript}`, {
    encoding: "utf-8",
    stdio: "pipe",
  });

  const secretMatch = output.match(/E2E_TOTP_SECRET=(.+)/);
  const totpSecret = secretMatch ? secretMatch[1].trim() : "";

  // Write the secret to a file that tests can import.
  const envPath = path.join(__dirname, ".e2e-env.json");
  writeFileSync(envPath, JSON.stringify({ totpSecret }, null, 2));

  console.log("E2E setup complete. TOTP secret captured for test users.");
}
