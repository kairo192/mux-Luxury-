#!/usr/bin/env node
// ============================================================================
// Builds the Tauri updater manifest (latest.json) for a signed Windows release.
//
// `tauri build` with createUpdaterArtifacts produces the NSIS installer and a
// detached `.sig` next to it, but NOT latest.json. This script:
//   1. finds the NSIS installer + .sig (and the MSI) under target/release/bundle,
//   2. copies them to release-assets/ under space-free names (GitHub rewrites
//      spaces in asset names, which would break the download URL),
//   3. writes release-assets/latest.json pointing at the tag's download URLs.
//
// Usage (CI):
//   node scripts/make-latest-json.mjs --version 1.2.0 --tag v1.2.0 \
//        --repo kairo192/mux-Luxury- [--notes "text"]
// ============================================================================

import { copyFileSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const appRoot = resolve(here, "..");

function arg(name, fallback = undefined) {
  const i = process.argv.indexOf(`--${name}`);
  if (i !== -1 && process.argv[i + 1] !== undefined) return process.argv[i + 1];
  return fallback;
}

const version = arg("version");
const tag = arg("tag", version ? `v${version}` : undefined);
const repo = arg("repo", process.env.GITHUB_REPOSITORY);
const notes = arg("notes", process.env.RELEASE_NOTES || `Mus Luxury CMS ${tag}`);
const bundleDir = resolve(appRoot, arg("bundle-dir", "src-tauri/target/release/bundle"));
const outDir = resolve(appRoot, arg("out", "release-assets"));

if (!version || !tag || !repo) {
  console.error("make-latest-json: --version, --tag and --repo (or GITHUB_REPOSITORY) are required");
  process.exit(2);
}

function findOne(dir, predicate, what) {
  if (!existsSync(dir)) {
    console.error(`make-latest-json: ${dir} does not exist (${what})`);
    process.exit(1);
  }
  const hits = readdirSync(dir).filter(predicate);
  if (hits.length !== 1) {
    console.error(`make-latest-json: expected exactly one ${what} in ${dir}, found: ${JSON.stringify(hits)}`);
    process.exit(1);
  }
  return join(dir, hits[0]);
}

const nsisDir = join(bundleDir, "nsis");
const installer = findOne(nsisDir, (f) => f.endsWith("-setup.exe") && f.includes(version), "NSIS installer");
const signaturePath = `${installer}.sig`;
if (!existsSync(signaturePath)) {
  console.error(`make-latest-json: ${signaturePath} missing — was the build run with createUpdaterArtifacts and TAURI_SIGNING_PRIVATE_KEY?`);
  process.exit(1);
}

mkdirSync(outDir, { recursive: true });
const installerName = `MusLuxuryCMS_${version}_x64-setup.exe`;
copyFileSync(installer, join(outDir, installerName));
copyFileSync(signaturePath, join(outDir, `${installerName}.sig`));

const msiDir = join(bundleDir, "msi");
if (existsSync(msiDir)) {
  for (const f of readdirSync(msiDir).filter((f) => f.endsWith(".msi") && f.includes(version))) {
    copyFileSync(join(msiDir, f), join(outDir, `MusLuxuryCMS_${version}_x64.msi`));
  }
}

const url = `https://github.com/${repo}/releases/download/${tag}/${installerName}`;
const signature = readFileSync(signaturePath, "utf8").trim();
const platform = { signature, url };

const manifest = {
  version,
  notes,
  pub_date: new Date().toISOString(),
  platforms: {
    "windows-x86_64": platform,
    "windows-x86_64-nsis": platform,
  },
};

writeFileSync(join(outDir, "latest.json"), JSON.stringify(manifest, null, 2) + "\n");
console.log(`make-latest-json: wrote ${join(outDir, "latest.json")} → ${url}`);
