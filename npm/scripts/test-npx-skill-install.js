const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const os = require("node:os");
const path = require("node:path");

const packageRoot = path.resolve(__dirname, "..", "..");
const npmCommand = process.platform === "win32" ? "npm.cmd" : "npm";
const npxCommand = process.platform === "win32" ? "npx.cmd" : "npx";
const tempRoot = fs.mkdtempSync(path.join(os.tmpdir(), "smart-search-npx-"));
const projectRoot = path.join(tempRoot, "project");
const npmCache = process.env.npm_config_cache || path.join(tempRoot, "npm-cache");

function run(command, args, options = {}) {
  const result = spawnSync(command, args, {
    cwd: options.cwd || packageRoot,
    encoding: "utf8",
    env: { ...process.env, npm_config_cache: npmCache },
    windowsHide: true
  });
  if (result.error || result.status !== 0) {
    process.stdout.write(result.stdout || "");
    process.stderr.write(result.stderr || "");
    throw result.error || new Error(`${command} exited with status ${result.status}`);
  }
  return result.stdout || "";
}

try {
  fs.mkdirSync(projectRoot, { recursive: true });
  const packed = JSON.parse(
    run(npmCommand, ["pack", "--json", "--pack-destination", tempRoot])
  );
  const tarball = path.join(tempRoot, packed[0].filename);

  run(npxCommand, [
    "--yes",
    `--package=${tarball}`,
    "smart-search",
    "skills",
    "update",
    "--targets",
    "codex",
    "--project-root",
    projectRoot,
    "--format",
    "json"
  ], { cwd: projectRoot });

  const installedRoot = path.join(projectRoot, ".codex", "skills", "smart-search-cli");
  const expectedFiles = [
    "SKILL.md",
    "agents/openai.yaml",
    "references/common.md",
    "references/docs.md",
    "references/fetch.md",
    "references/map.md",
    "references/search.md"
  ];
  for (const relativePath of expectedFiles) {
    if (!fs.existsSync(path.join(installedRoot, relativePath))) {
      throw new Error(`npx skill installation did not create ${relativePath}`);
    }
  }
} finally {
  fs.rmSync(tempRoot, { recursive: true, force: true });
}
