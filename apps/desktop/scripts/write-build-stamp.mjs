/**
 * Writes apps/desktop/build/install-stamp.json with the git ref the desktop
 * .exe should pin to at first-launch bootstrap time.  This file ships inside
 * the packaged app via electron-builder's extraResources entry and is read
 * by electron/main.ts to drive the install.ps1 stage bootstrap flow.
 *
 * Schema (subject to bump via STAMP_SCHEMA_VERSION):
 *   {
 *     "schemaVersion": 1,
 *     "commit":        "<40-char SHA>",
 *     "branch":        "<branch name>",
 *     "repo":          "<OWNER/REPO GitHub slug the scripts/repo were built from>",
 *     "builtAt":       "<ISO 8601 UTC timestamp>",
 *     "dirty":         true|false,
 *     "source":        "ci" | "local" | "fallback"
 *   }
 *
 * The `repo` field is what makes first-launch bootstrap fork-aware: the
 * Electron bootstrap runner (bootstrap-runner.ts) and the Tauri bootstrap
 * installer (install_script.rs) resolve install.ps1/install.sh download URLs
 * from it instead of a hardcoded upstream slug.  Precedence:
 *   1. $MOOR_GITHUB_REPO / $MOOR_GITHUB_FORK (explicit Moor fork override)
 *   2. $GITHUB_REPOSITORY (CI canonical slug)
 *   3. `git remote get-url origin` parsed to OWNER/REPO (local builds)
 *   4. UPSTREAM_REPO fallback (non-git trees; preserves legacy behaviour)
 *
 * Source preference order (commit/branch):
 *   1. CI env vars ($GITHUB_SHA / $GITHUB_REF_NAME) -- avoid edge cases with
 *      shallow clones, detached HEADs, etc. in CI.
 *   2. Local `git rev-parse` against the parent repo (../..).
 *   3. Fallback stamp for local/personal builds from non-git source trees
 *      (ZIP extract, interrupted clone with no HEAD, etc.).
 *
 * Dev / out-of-repo builds without git produce an explicit fallback stamp
 * rather than aborting the whole build.  Bootstrap treats the all-zero
 * commit as unpinned and follows the branch instead of fetching a fake SHA.
 */

import { mkdirSync, writeFileSync } from "fs"
import { resolve, join, relative } from "path"
import { execSync } from "child_process"

import { isMain } from "./utils.mjs"

const STAMP_SCHEMA_VERSION = 1

/** Upstream slug kept as the last-resort default so legacy builds keep working. */
export const UPSTREAM_REPO = 'NousResearch/hermes-agent'

/** All-zero placeholder used when no real commit can be resolved. */
export const FALLBACK_COMMIT = "0000000000000000000000000000000000000000"
export const FALLBACK_BRANCH = "main"

const DESKTOP_ROOT = resolve(import.meta.dirname, "..")
const REPO_ROOT = resolve(DESKTOP_ROOT, "..", "..")
const OUT_DIR = join(DESKTOP_ROOT, "build")
const OUT_FILE = join(OUT_DIR, "install-stamp.json")

function tryExec(cmd, opts) {
  try {
    return execSync(cmd, { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"], ...opts }).trim()
  } catch {
    return null
  }
}

export function fromCI(env = process.env) {
  const sha = env.GITHUB_SHA
  if (!sha) return null
  const branch = env.GITHUB_REF_NAME || env.GITHUB_HEAD_REF || null
  return {
    commit: sha,
    branch: branch,
    dirty: false, // CI builds from a checkout-of-ref by definition
    source: "ci"
  }
}

export function fromLocalGit(repoRoot = REPO_ROOT, execFn = tryExec) {
  const sha = execFn("git rev-parse HEAD", { cwd: repoRoot })
  if (!sha) return null
  const branch = execFn("git rev-parse --abbrev-ref HEAD", { cwd: repoRoot })
  // `git status --porcelain -uno` is empty iff tracked files match HEAD.
  // We exclude untracked files (-uno) intentionally: a developer who's
  // checked out an installer scratch dir alongside the repo shouldn't
  // poison every local build with a [DIRTY] stamp.  We DO care about
  // tracked-but-modified files because those mean the .exe content
  // differs from the commit being pinned.
  const status = execFn("git status --porcelain -uno", { cwd: repoRoot })
  const dirty = status !== null && status.length > 0
  return {
    commit: sha,
    branch: branch === "HEAD" ? null : branch, // detached HEAD -> null
    dirty: dirty,
    source: "local"
  }
}

export function fromFallback(branch = FALLBACK_BRANCH) {
  // Non-git builds (ZIP download, bootstrap installer without a resolvable
  // HEAD) cannot determine a real commit.  Use a placeholder so local /
  // personal builds can still complete.  The desktop bootstrap treats the
  // all-zero commit as "unknown" and falls back to an unpinned branch
  // bootstrap instead of trying to fetch a non-existent GitHub commit.
  return {
    commit: FALLBACK_COMMIT,
    branch: branch || FALLBACK_BRANCH,
    dirty: false,
    source: "fallback"
  }
}

/**
 * Parse a git remote URL to an `OWNER/REPO` slug.  Handles the three common
 * forms (https, scp-like ssh, ssh://).  Returns null when unparseable so the
 * caller falls through to the next repo-resolution rung.
 */
export function parseRepoSlug(remoteUrl) {
  if (!remoteUrl || typeof remoteUrl !== "string") return null
  const trimmed = remoteUrl.trim()
  const m =
    trimmed.match(/github\.com[:/]([^/\s]+\/[^/\s]+?)(?:\.git)?\s*$/i)
  if (!m) return null
  // Guard against trailing path segments (e.g. /tree/main pasted by accident).
  const slug = m[1].replace(/\/+$/, "")
  if (!/^[^/\s]+\/[^/\s]+$/.test(slug) || slug.includes("/tree/")) return null
  return slug
}

/**
 * Resolve the `OWNER/REPO` slug the packaged app should fetch install
 * scripts from when no bundled copy satisfies the request.  Pure enough for
 * unit tests: inject env / execFn / repoRoot.
 */
export function resolveRepoSlug({
  env = process.env,
  repoRoot = REPO_ROOT,
  execFn = tryExec,
} = {}) {
  const explicit =
    (env.MOOR_GITHUB_REPO || "").trim() || (env.MOOR_GITHUB_FORK || "").trim()
  if (explicit) return explicit.replace(/\/+$/, "")
  const ciRepo = (env.GITHUB_REPOSITORY || "").trim()
  if (ciRepo && /^[^/\s]+\/[^/\s]+$/.test(ciRepo)) return ciRepo
  const remote = execFn("git remote get-url origin", { cwd: repoRoot })
  return parseRepoSlug(remote) || UPSTREAM_REPO
}

/**
 * Resolve the install stamp without writing it.  Pure enough for unit tests:
 * inject env / execFn / repoRoot to simulate CI, local git, or no-git trees.
 */
export function resolveStamp({
  env = process.env,
  repoRoot = REPO_ROOT,
  execFn = tryExec,
  fallbackBranch = FALLBACK_BRANCH
} = {}) {
  const base = fromCI(env) || fromLocalGit(repoRoot, execFn) || fromFallback(fallbackBranch)
  return { ...base, repo: resolveRepoSlug({ env, repoRoot, execFn }) }
}

export function isFallbackCommit(commit) {
  return typeof commit === "string" && /^0{7,40}$/.test(commit)
}

function main() {
  const stamp = resolveStamp()
  if (!stamp || !stamp.commit) {
    // Should not happen — fromFallback() always provides a commit.
    console.error(
      "[write-build-stamp] ERROR: could not determine git commit.\n" +
        "  - $GITHUB_SHA not set\n" +
        "  - `git rev-parse HEAD` failed at " +
        REPO_ROOT +
        "\n" +
        "Packaged builds require a git ref to pin first-launch install.ps1\n" +
        "against. Run from a git checkout or set $GITHUB_SHA explicitly."
    )
    process.exit(1)
  }

  if (isFallbackCommit(stamp.commit)) {
    console.warn(
      "[write-build-stamp] WARNING: no git commit found (non-git checkout?).\n" +
        "  Using placeholder commit — the packaged app will fall back to the\n" +
        "  default branch for first-launch bootstrap.  For production builds,\n" +
        "  run from a git checkout or set $GITHUB_SHA."
    )
  }

  if (stamp.dirty) {
    console.warn(
      "[write-build-stamp] WARNING: working tree is dirty.\n" +
        "  Pinning to " +
        stamp.commit.slice(0, 12) +
        " but the packaged code may differ from that commit.\n" +
        "  Commit your changes before publishing this build."
    )
  }

  const payload = {
    schemaVersion: STAMP_SCHEMA_VERSION,
    commit: stamp.commit,
    branch: stamp.branch,
    repo: stamp.repo || UPSTREAM_REPO,
    builtAt: new Date().toISOString(),
    dirty: stamp.dirty,
    source: stamp.source
  }

  mkdirSync(OUT_DIR, { recursive: true })
  writeFileSync(OUT_FILE, JSON.stringify(payload, null, 2) + "\n", "utf8")
  console.log(
    "[write-build-stamp] wrote " +
      relative(REPO_ROOT, OUT_FILE) +
      " -> " +
      stamp.commit.slice(0, 12) +
      (stamp.branch ? " (" + stamp.branch + ")" : "") +
      " [" + (stamp.repo || UPSTREAM_REPO) + "]" +
      (stamp.dirty ? " [DIRTY]" : "") +
      (stamp.source === "fallback" ? " [FALLBACK]" : "")
  )
}

if (isMain(import.meta.url)) {
  main()
}
