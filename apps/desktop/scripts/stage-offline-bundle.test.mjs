import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

import { stageInstallScripts, verifyOfflineBundle } from './stage-offline-bundle.mjs'

test('stageInstallScripts stages byte-identical copies of both install scripts', () => {
  const dir = mkdtempSync(join(tmpdir(), 'moor-offline-stage-'))
  try {
    const staged = stageInstallScripts({ outDir: join(dir, 'offline-scripts') })
    assert.equal(staged.length, 2)
    assert.deepEqual(
      staged.map(s => s.name).sort(),
      ['install.ps1', 'install.sh']
    )
    for (const s of staged) {
      assert.ok(s.bytes > 10_000, `${s.name} suspiciously small (${s.bytes} bytes)`)
      assert.match(s.sha256, /^[0-9a-f]{64}$/)
      assert.ok(existsSync(join(dir, 'offline-scripts', s.name)))
    }
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('verifyOfflineBundle fails loudly when the bundle was never staged', () => {
  const dir = mkdtempSync(join(tmpdir(), 'moor-offline-empty-'))
  try {
    assert.throws(
      () => verifyOfflineBundle({ buildDir: dir }),
      /MISSING.*repo\.zip/
    )
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('verifyOfflineBundle rejects a truncated repo.zip', () => {
  const dir = mkdtempSync(join(tmpdir(), 'moor-offline-tiny-'))
  try {
    writeFileSync(join(dir, 'repo.zip'), Buffer.alloc(16))
    assert.throws(
      () => verifyOfflineBundle({ buildDir: dir }),
      /SUSPICIOUS/
    )
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('verifyOfflineBundle rejects staged scripts that drifted from source', () => {
  const dir = mkdtempSync(join(tmpdir(), 'moor-offline-stale-'))
  try {
    // Plausible-size zip so the check proceeds to the scripts rung.
    writeFileSync(join(dir, 'repo.zip'), Buffer.alloc(2 * 1024 * 1024))
    const scriptsDir = join(dir, 'offline-scripts')
    mkdirSync(scriptsDir, { recursive: true })
    writeFileSync(join(scriptsDir, 'install.ps1'), 'stale')
    writeFileSync(join(scriptsDir, 'install.sh'), 'stale')
    assert.throws(
      () => verifyOfflineBundle({ buildDir: dir }),
      /STALE/
    )
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('verifyOfflineBundle accepts a fresh, complete bundle', () => {
  const dir = mkdtempSync(join(tmpdir(), 'moor-offline-ok-'))
  try {
    // Plausible-size zip (content is not inspected — size + collector sanity is).
    writeFileSync(join(dir, 'repo.zip'), Buffer.alloc(2 * 1024 * 1024))
    stageInstallScripts({ outDir: join(dir, 'offline-scripts') })
    // A minimal stamp: presence is what is checked here.
    writeFileSync(
      join(dir, 'install-stamp.json'),
      JSON.stringify({ schemaVersion: 1, commit: 'a'.repeat(40), branch: 'main' })
    )
    const summary = verifyOfflineBundle({ buildDir: dir })
    assert.equal(summary.repoZipBytes, 2 * 1024 * 1024)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})
