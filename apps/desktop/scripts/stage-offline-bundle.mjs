/**
 * stage-offline-bundle.mjs
 *
 * Builds + verifies the fully-offline first-launch payload that ships INSIDE
 * the desktop .exe via electron-builder `extraResources`:
 *
 *   build/repo.zip                 full Moor codebase (no .git, no node_modules,
 *                                  no venvs) for the `repository` stage
 *   build/offline-scripts/         byte-identical copies of scripts/install.ps1
 *                                  + scripts/install.sh for the bootstrap runner
 *   build/offline-manifest.json    hashes/sizes so the packaged app + CI can
 *                                  prove the bundle is fresh and complete
 *   build/install-stamp.json       commit/branch/repo pin (written by
 *                                  write-build-stamp.mjs; verified here, not
 *                                  overwritten)
 *
 * Why this exists: packaged desktop builds used to ship NONE of the above.
 * First launch therefore HAD to download install.ps1 from
 * raw.githubusercontent.com at the stamped commit, and install.ps1 itself had
 * to `git clone` the repo.  On an offline machine — or behind a 429-throttled
 * raw host (the "Moor couldn't start / Failed to download install.ps1: HTTP
 * 429" failure) — bootstrap died before stage 1.  With this bundle staged and
 * listed in `extraResources`, the bootstrap runner resolves `bundled` before
 * `download`, and install.ps1 unpacks `$env:MOOR_BUNDLED_REPO` instead of
 * cloning.  No network is needed to reach the `repository` stage or run it.
 *
 * Honest scope note: stages AFTER `repository` (uv/python/node/git binaries,
 * `uv sync` from PyPI, `npm ci` from the npm registry) still need the network
 * on a truly fresh machine unless their own caches are pre-seeded.  What this
 * bundle guarantees is: the app NEVER fails for lack of install.ps1/sh or the
 * Moor source tree itself, and every later network failure surfaces as that
 * stage's own clear error — never as a cryptic bootstrap-download 429.
 *
 * Wired into `npm run build` (package.json) and scripts/build-desktop-exe.ps1
 * (the 1-click compiler), so every .exe contains a fresh bundle.  Run:
 *
 *   node scripts/stage-offline-bundle.mjs          # build + verify
 *   node scripts/stage-offline-bundle.mjs --verify # verify only (CI / BAT)
 */

import { createHash } from 'node:crypto'
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  readFileSync,
  statSync,
  writeFileSync
} from 'node:fs'
import { join, relative, resolve } from 'node:path'

import { buildRepoArchive, collectRepoFiles } from './bundle-repo-archive.mjs'
import { isMain } from './utils.mjs'

const DESKTOP_ROOT = resolve(import.meta.dirname, '..')
const REPO_ROOT = resolve(DESKTOP_ROOT, '..', '..')
const BUILD_DIR = join(DESKTOP_ROOT, 'build')
const REPO_ZIP = join(BUILD_DIR, 'repo.zip')
const SCRIPTS_DIR = join(BUILD_DIR, 'offline-scripts')
const MANIFEST_PATH = join(BUILD_DIR, 'offline-manifest.json')
const STAMP_PATH = join(BUILD_DIR, 'install-stamp.json')

const SOURCE_SCRIPTS = ['install.ps1', 'install.sh']

export function sha256OfFile(filePath) {
  const hash = createHash('sha256')
  hash.update(readFileSync(filePath))
  return hash.digest('hex')
}

function readStamp() {
  try {
    return JSON.parse(readFileSync(STAMP_PATH, 'utf8'))
  } catch {
    return null
  }
}

/**
 * Stage byte-identical copies of the source install scripts next to repo.zip.
 * Returns [{ name, bytes, sha256 }].
 */
export function stageInstallScripts({
  repoRoot = REPO_ROOT,
  outDir = SCRIPTS_DIR
} = {}) {
  mkdirSync(outDir, { recursive: true })
  return SOURCE_SCRIPTS.map(name => {
    const src = join(repoRoot, 'scripts', name)
    if (!existsSync(src)) {
      throw new Error(`[stage-offline-bundle] missing source script: ${src}`)
    }
    const dest = join(outDir, name)
    copyFileSync(src, dest)
    const { size } = statSync(dest)
    return { name, bytes: size, sha256: sha256OfFile(dest) }
  })
}

/**
 * Verify a staged offline bundle without rebuilding it.  Throws on the first
 * problem with an actionable message; returns the manifest summary on success.
 */
export function verifyOfflineBundle({
  buildDir = BUILD_DIR,
  repoRoot = REPO_ROOT
} = {}) {
  const repoZip = join(buildDir, 'repo.zip')
  const scriptsDir = join(buildDir, 'offline-scripts')
  const manifestPath = join(buildDir, 'offline-manifest.json')
  const stampPath = join(buildDir, 'install-stamp.json')

  if (!existsSync(repoZip)) {
    throw new Error(
      `[stage-offline-bundle] MISSING ${relative(repoRoot, repoZip)} — run \`node scripts/stage-offline-bundle.mjs\` (or the 1-click build-desktop-exe.bat) before packaging. Without it the .exe must download the repo from GitHub on first launch and cannot install offline.`
    )
  }
  const zipStat = statSync(repoZip)
  if (zipStat.size < 1024 * 1024) {
    throw new Error(
      `[stage-offline-bundle] SUSPICIOUS ${relative(repoRoot, repoZip)} (${zipStat.size} bytes < 1 MB) — likely a truncated build. Delete build/repo.zip and re-run the stager.`
    )
  }

  // The zip must actually contain the files the repository stage needs.
  const relPaths = new Set(collectRepoFiles(repoRoot).map(f => f.relPath))
  for (const required of ['pyproject.toml', 'scripts/install.ps1', 'scripts/install.sh', 'moor_bootstrap.py']) {
    if (!relPaths.has(required)) {
      throw new Error(
        `[stage-offline-bundle] repo collector no longer yields ${required} — the packaged repository stage would be broken. Fix collectRepoFiles() in bundle-repo-archive.mjs.`
      )
    }
  }

  for (const name of SOURCE_SCRIPTS) {
    const staged = join(scriptsDir, name)
    const src = join(repoRoot, 'scripts', name)
    if (!existsSync(staged)) {
      throw new Error(
        `[stage-offline-bundle] MISSING ${relative(repoRoot, staged)} — re-run the stager.`
      )
    }
    if (existsSync(src) && sha256OfFile(staged) !== sha256OfFile(src)) {
      throw new Error(
        `[stage-offline-bundle] STALE ${relative(repoRoot, staged)} (hash differs from scripts/${name}) — re-run the stager so the .exe ships the current installer.`
      )
    }
  }

  if (!existsSync(stampPath)) {
    throw new Error(
      `[stage-offline-bundle] MISSING ${relative(repoRoot, stampPath)} — run \`node scripts/write-build-stamp.mjs\` first.`
    )
  }

  if (existsSync(manifestPath)) {
    const manifest = JSON.parse(readFileSync(manifestPath, 'utf8'))
    const zipHash = sha256OfFile(repoZip)
    if (manifest.repoZip && manifest.repoZip.sha256 && manifest.repoZip.sha256 !== zipHash) {
      throw new Error(
        `[stage-offline-bundle] STALE offline-manifest.json (repo.zip hash moved) — re-run the stager.`
      )
    }
  }

  return { repoZipBytes: zipStat.size }
}

export function stageOfflineBundle({ repoRoot = REPO_ROOT } = {}) {
  const stamp = readStamp()
  if (!stamp) {
    throw new Error(
      '[stage-offline-bundle] build/install-stamp.json not found — run `node scripts/write-build-stamp.mjs` first (npm run build already orders this).'
    )
  }

  const archive = buildRepoArchive({ repoRoot, outZipPath: REPO_ZIP })
  const scripts = stageInstallScripts({ repoRoot })

  const manifest = {
    schemaVersion: 1,
    builtAt: new Date().toISOString(),
    stamp: {
      commit: stamp.commit || null,
      branch: stamp.branch || null,
      repo: stamp.repo || null,
      source: stamp.source || null
    },
    repoZip: {
      path: 'build/repo.zip',
      resourceName: 'repo.zip',
      bytes: archive.sizeBytes,
      sha256: sha256OfFile(REPO_ZIP),
      files: archive.fileCount
    },
    scripts: scripts.map(s => ({ ...s, path: `build/offline-scripts/${s.name}`, resourceName: `scripts/${s.name}` }))
  }
  mkdirSync(BUILD_DIR, { recursive: true })
  writeFileSync(MANIFEST_PATH, JSON.stringify(manifest, null, 2) + '\n', 'utf8')

  const sizeMb = (archive.sizeBytes / (1024 * 1024)).toFixed(2)
  console.log(
    `[stage-offline-bundle] offline-ready: repo.zip (${archive.fileCount} files, ${sizeMb} MB) + ${scripts.length} install scripts + stamp ${String(stamp.commit || '').slice(0, 12)} [${stamp.repo || 'unknown repo'}]`
  )
  verifyOfflineBundle({ buildDir: BUILD_DIR, repoRoot })
  return manifest
}

function main() {
  const args = new Set(process.argv.slice(2))
  if (args.has('--verify')) {
    const summary = verifyOfflineBundle()
    console.log(
      `[stage-offline-bundle] verified offline bundle (${(summary.repoZipBytes / (1024 * 1024)).toFixed(2)} MB repo.zip + staged install scripts + stamp)`
    )
    return
  }
  stageOfflineBundle()
}

if (isMain(import.meta.url)) {
  main()
}
