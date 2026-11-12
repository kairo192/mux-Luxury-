// Starts a FRESH production-mode API for the end-to-end tests.
// - SQLite (default): a new empty database file in a temporary folder.
// - PostgreSQL: set E2E_DATABASE_URL to an EMPTY database (CI service DB).
// Secrets are random per run; nothing here is a real key.
import { spawn } from "node:child_process";
import { mkdtempSync, mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { randomBytes } from "node:crypto";

const root = resolve(import.meta.dirname, "..", "..");
const work = mkdtempSync(join(tmpdir(), "luxe-e2e-"));
mkdirSync(join(work, "uploads"));
mkdirSync(join(work, "backups"));

const env = {
  ...process.env,
  APP_ENV: "production",
  SECRET_KEY: randomBytes(48).toString("hex"),
  BACKUP_ENCRYPTION_KEY: randomBytes(32).toString("base64"),
  UPLOAD_DIR: join(work, "uploads"),
  BACKUP_DIR: join(work, "backups"),
  CORS_ORIGINS: `${process.env.E2E_CMS_URL},${process.env.E2E_SHOP_URL}`,
  STOREFRONT_INTERNAL_URL: process.env.E2E_SHOP_URL,
  PYTHONUNBUFFERED: "1",
  // The browser tests log in dozens of times from one machine; production
  // keeps the default brute-force limit (5 per minute).
  LOGIN_ATTEMPTS_PER_MINUTE: "500",
};
if (process.env.E2E_DATABASE_URL) {
  env.LUXE_DB_ENGINE = "postgres";
  env.DATABASE_URL = process.env.E2E_DATABASE_URL;
} else {
  env.LUXE_DB_ENGINE = "sqlite";
  env.LUXE_SQLITE_PATH = join(work, "e2e.sqlite3");
}
console.log(`[e2e] API data in ${work} (${env.LUXE_DB_ENGINE})`);

const port = new URL(process.env.E2E_API_URL).port;
const child = spawn(process.env.PYTHON || "python3",
  ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", port],
  { cwd: join(root, "backend"), env, stdio: "inherit" });
for (const sig of ["SIGINT", "SIGTERM"]) process.on(sig, () => child.kill(sig));
child.on("exit", (code) => process.exit(code ?? 0));
