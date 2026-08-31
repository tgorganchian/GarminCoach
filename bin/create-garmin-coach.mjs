#!/usr/bin/env node

import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const sourceRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");

function scaffoldFiles(root) {
  const manifest = JSON.parse(readFileSync(resolve(root, "package.json"), "utf8"));
  const declaredFiles = manifest.files;
  const excluded = manifest.garminCoach?.scaffoldExclude ?? [];
  if (!Array.isArray(declaredFiles) || !Array.isArray(excluded)) {
    throw new Error("package.json must declare files and garminCoach.scaffoldExclude arrays.");
  }
  return declaredFiles
    .filter((entry) => !excluded.some((prefix) => entry === prefix || entry.startsWith(prefix)))
    .flatMap((entry) => expandDeclaredFile(root, entry));
}

function expandDeclaredFile(root, entry) {
  if (!entry.includes("*")) return [entry];
  const match = entry.match(/^(.+)\/\*\.([A-Za-z0-9]+)$/);
  if (!match) throw new Error(`Unsupported package file pattern: ${entry}`);
  const [, directory, extension] = match;
  return readdirSync(resolve(root, directory), { withFileTypes: true })
    .filter((file) => file.isFile() && file.name.endsWith(`.${extension}`))
    .map((file) => `${directory}/${file.name}`);
}

export function createProject(destination, root = sourceRoot) {
  if (!destination) throw new Error("Usage: create-garmin-coach <directory>");
  const target = resolve(destination);
  if (target === resolve(root)) throw new Error("Destination cannot be the package source directory.");
  if (existsSync(target) && readdirSync(target).length > 0) {
    throw new Error(`Destination must be empty: ${target}`);
  }
  mkdirSync(target, { recursive: true });
  for (const relative of scaffoldFiles(root)) {
    const source = resolve(root, relative);
    if (!existsSync(source)) throw new Error(`Package is missing required public file: ${relative}`);
    const destination = resolve(target, relative);
    mkdirSync(dirname(destination), { recursive: true });
    cpSync(source, destination, {
      recursive: true,
      filter: (entry) => !entry.includes("__pycache__") && !entry.endsWith(".pyc"),
    });
  }
  copyFile(root, target, ".env.example", ".env");
  copyFile(root, target, "athlete_config.example.py", "athlete_config.py");
  copyFile(root, target, "templates/project.gitignore", ".gitignore");
  for (const name of ["athlete-profile.md", "coach-log.md", "training-plan.md"]) {
    copyFile(root, target, `templates/coaching/${name}`, `coaching/${name}`);
  }
  mkdirSync(resolve(target, "coaching/journal"), { recursive: true });
  copyFile(root, target, "templates/coaching/journal/README.md", "coaching/journal/README.md");
  return target;
}

function copyFile(root, target, sourceRelative, targetRelative) {
  const contents = readFileSync(resolve(root, sourceRelative));
  const output = resolve(target, targetRelative);
  mkdirSync(dirname(output), { recursive: true });
  writeFileSync(output, contents);
}

export function main(argv) {
  if (argv.length !== 1) throw new Error("Usage: create-garmin-coach <directory>");
  const target = createProject(argv[0]);
  console.log(`Created GarminCoach workspace in ${target}`);
  console.log("Next: open the workspace with a supported coaching agent to begin guided setup.");
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    main(process.argv.slice(2));
  } catch (error) {
    console.error(error.message);
    process.exitCode = 1;
  }
}
