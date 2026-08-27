/**
 * bundle-repo-archive.mjs
 *
 * Packages the Moor repository into apps/desktop/build/repo.zip so that the
 * packaged desktop installer and executable contain a complete, offline-ready
 * copy of the Moor Agent codebase.
 *
 * This enables the first-launch bootstrap installer (`install.ps1` / `install.sh`)
 * to unpack and initialize Moor locally without requiring any network access
 * to GitHub (SSH, HTTPS, or ZIP download).
 */

import { existsSync, mkdirSync, statSync, readdirSync, readFileSync, writeFileSync } from 'node:fs'
import { resolve, join, relative } from 'node:path'
import * as fflate from 'fflate'

import { isMain } from './utils.mjs'

const DESKTOP_ROOT = resolve(import.meta.dirname, '..')
const REPO_ROOT = resolve(DESKTOP_ROOT, '..', '..')
const OUT_DIR = join(DESKTOP_ROOT, 'build')
const OUT_ZIP = join(OUT_DIR, 'repo.zip')

// Directories to completely skip
const EXCLUDED_DIRS = new Set([
  '.git',
  '.github',
  '.pytest_cache',
  '.venv',
  'venv',
  'node_modules',
  '__pycache__',
  'release',
  'dist',
  'build',
  'apps', // apps/desktop and apps/bootstrap-installer are build-time containers
  'tests', // keep repo lean for runtime
  'tests-js',
  'evals',
  'experiments',
  'mcp-research-data',
  'contributors',
  'datagen-config-examples'
])

// File patterns to skip
const EXCLUDED_EXTENSIONS = new Set([
  '.pyc',
  '.pyo',
  '.pyd',
  '.log',
  '.tmp',
  '.bak',
  '.DS_Store'
])

const EXCLUDED_FILENAMES = new Set([
  'Thumbs.db',
  '.bytecode-fingerprint',
  'test_durations.json',
  '.moor-bootstrap-complete'
])

/**
 * Collect all files in the repository to include in the bundle.
 */
export function collectRepoFiles(rootDir = REPO_ROOT) {
  const files = []

  function walk(currentDir) {
    const entries = readdirSync(currentDir, { withFileTypes: true })
    for (const entry of entries) {
      const name = entry.name
      const fullPath = join(currentDir, name)
      const relPath = relative(rootDir, fullPath).replace(/\\/g, '/')

      if (entry.isDirectory()) {
        if (EXCLUDED_DIRS.has(name) || name.startsWith('.git') || name.startsWith('.venv')) {
          continue
        }
        walk(fullPath)
      } else if (entry.isFile()) {
        if (EXCLUDED_FILENAMES.has(name)) continue
        const dotIdx = name.lastIndexOf('.')
        if (dotIdx !== -1) {
          const ext = name.slice(dotIdx)
          if (EXCLUDED_EXTENSIONS.has(ext)) continue
        }
        files.push({ fullPath, relPath })
      }
    }
  }

  walk(rootDir)

  // Also include apps/shared if it exists (shared TypeScript definitions)
  const sharedDir = join(rootDir, 'apps', 'shared')
  if (existsSync(sharedDir)) {
    function walkShared(dir) {
      const entries = readdirSync(dir, { withFileTypes: true })
      for (const entry of entries) {
        const fullPath = join(dir, entry.name)
        const relPath = relative(rootDir, fullPath).replace(/\\/g, '/')
        if (entry.isDirectory()) {
          if (entry.name === 'node_modules' || entry.name === 'dist') continue
          walkShared(fullPath)
        } else if (entry.isFile()) {
          files.push({ fullPath, relPath })
        }
      }
    }
    walkShared(sharedDir)
  }

  return files
}

/**
 * Build the repo.zip archive using fflate.
 */
export function buildRepoArchive({
  repoRoot = REPO_ROOT,
  outZipPath = OUT_ZIP,
  compressionLevel = 6
} = {}) {
  const files = collectRepoFiles(repoRoot)
  const zipData = {}

  for (const file of files) {
    const content = readFileSync(file.fullPath)
    zipData[file.relPath] = content
  }

  const zipped = fflate.zipSync(zipData, { level: compressionLevel })

  mkdirSync(OUT_DIR, { recursive: true })
  writeFileSync(outZipPath, zipped)

  const sizeMb = (zipped.length / (1024 * 1024)).toFixed(2)
  console.log(`[bundle-repo-archive] packaged ${files.length} files into ${outZipPath} (${sizeMb} MB)`)

  return {
    path: outZipPath,
    fileCount: files.length,
    sizeBytes: zipped.length
  }
}

if (isMain(import.meta.url)) {
  buildRepoArchive()
}
