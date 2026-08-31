import assert from "node:assert/strict";
import { mkdtempSync, mkdirSync, readdirSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFileSync } from "node:child_process";
import test from "node:test";

import { createProject, main } from "../bin/create-garmin-coach.mjs";

const npm = process.platform === "win32" ? "npm.cmd" : "npm";

function isIgnored(cwd, path) {
  try {
    execFileSync("git", ["check-ignore", "--no-index", "-q", path], { cwd, encoding: "utf8" });
    return true;
  } catch (error) {
    if (error.status === 1) return false;
    throw error;
  }
}

test("scaffold creates generic local coaching state", () => {
  const root = mkdtempSync(join(tmpdir(), "garmin-coach-test-"));
  const target = join(root, "workspace");
  try {
    createProject(target);
    assert.ok(readdirSync(join(target, "coaching")).includes("training-plan.md"));
    assert.ok(readdirSync(join(target, "coaching", "journal")).includes("README.md"));
    assert.ok(readdirSync(target).includes(".gitignore"));
    assert.ok(readdirSync(target).includes("package.json"));
    assert.ok(readdirSync(target).includes(".env.example"));
    assert.ok(readdirSync(target).includes("tests"));
    assert.ok(!readdirSync(join(target, "tests")).includes("__pycache__"));
    assert.ok(readdirSync(join(target, "examples", "coaching", "journal")).includes("2026-W15.md"));
    assert.ok(readdirSync(target).includes("GUIDE.md"));
    assert.ok(readdirSync(target).includes("garmin_coach"));
    assert.ok(readdirSync(join(target, "examples", "coaching", "journal")).includes("2026-W15.md"));
    assert.ok(!readdirSync(target).includes("docs"));
    assert.match(execFileSync("python", ["release_audit.py"], { cwd: target, encoding: "utf8" }), /passed/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("CLI validates its one destination argument", () => {
  assert.throws(() => main([]), /Usage/);
  assert.throws(() => main(["one", "two"]), /Usage/);
});

test("scaffold protects a non-empty destination", () => {
  const root = mkdtempSync(join(tmpdir(), "garmin-coach-test-"));
  const target = join(root, "workspace");
  mkdirSync(target);
  writeFileSync(join(target, "existing.txt"), "keep");
  try {
    assert.throws(() => createProject(target), /must be empty/);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("workspace ignores local coaching state but not public examples", () => {
  const root = mkdtempSync(join(tmpdir(), "garmin-coach-ignore-"));
  const target = join(root, "workspace");
  try {
    createProject(target);
    execFileSync("git", ["init", "-q"], { cwd: target, encoding: "utf8" });
    assert.equal(isIgnored(target, "coaching/journal/README.md"), true);
    assert.equal(isIgnored(target, "tests/__pycache__/marker.txt"), true);
    assert.equal(isIgnored(target, "examples/coaching/athlete-profile.md"), false);
    assert.equal(isIgnored(process.cwd(), "templates/coaching/athlete-profile.md"), false);
    assert.equal(isIgnored(process.cwd(), "tests/__pycache__/marker.txt"), true);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});

test("packed artifact is private-safe and its installed scaffold works", () => {
  const root = mkdtempSync(join(tmpdir(), "garmin-coach-package-"));
  const archiveDirectory = join(root, "archive");
  const installed = join(root, "installed");
  const target = join(root, "workspace");
  mkdirSync(archiveDirectory);
  try {
    const [packed] = JSON.parse(execFileSync(npm, ["pack", "--json", "--pack-destination", archiveDirectory], {
      cwd: process.cwd(),
      encoding: "utf8",
      shell: process.platform === "win32",
    }));
    const packedPaths = packed.files.map((file) => file.path);
    assert.ok(packedPaths.includes("GUIDE.md"));
    assert.ok(packedPaths.includes(".env.example"));
    assert.ok(!packedPaths.some((path) => path.startsWith("docs/") || path.startsWith("skill/") || path === "create_workouts.py"));

    const archive = join(archiveDirectory, packed.filename);
    execFileSync(npm, ["install", "--ignore-scripts", "--no-audit", "--no-fund", "--no-package-lock", "--prefix", installed, archive], {
      cwd: process.cwd(),
      encoding: "utf8",
      shell: process.platform === "win32",
    });
    execFileSync(process.execPath, [join(installed, "node_modules", "create-garmin-coach", "bin", "create-garmin-coach.mjs"), target], {
      cwd: installed,
      encoding: "utf8",
    });
    assert.ok(readdirSync(target).includes("GUIDE.md"));
    assert.ok(readdirSync(target).includes("garmin_coach"));
    assert.ok(!readdirSync(target).includes("docs"));
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
