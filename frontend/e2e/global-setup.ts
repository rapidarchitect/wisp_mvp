import { execSync } from "child_process";

const setupScript = new URL("./setup.py", import.meta.url).pathname;

export default async function globalSetup() {
  // Seed the demo tenant and deterministic test users.
  execSync(`cd ../ && uv run python ${setupScript}`, {
    encoding: "utf-8",
    stdio: "pipe",
  });

  console.log("E2E setup complete. Demo tenant and test users seeded.");
}
