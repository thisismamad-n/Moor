import assert from 'node:assert/strict'
import { mkdtempSync, mkdirSync, rmSync, writeFileSync, existsSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import test from 'node:test'

import { assertInstallPs1Parses, findPowerShell, stageInstallScripts, verifyOfflineBundle } from './stage-offline-bundle.mjs'

function hasPowerShell() {
  return findPowerShell() !== null
}

// Minimal reproduction of the 2026-09-22 field failure: the dependency-tier
// `foreach ($tier in $installTiers) {` opener was dropped by a merge while the
// loop body (and its closing brace) survived. The stray `}` closes the
// enclosing `try` early, so the file reports MissingCatchOrFinally plus
// UnexpectedToken — exactly the user's desktop.log signature.
const BROKEN_TIER_BLOCK = `function Install-Dependencies {
    try {
        $installed = $false
        if (-not $installed) {
            Write-Host "Trying tier..."
            if ($true) {
                $installed = $true
            }
        }
    }
    if (-not $installed) {
        throw "Failed"
    }
    } catch {
        throw
    }
}
`

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

test('assertInstallPs1Parses rejects the 2026-09-22 dropped-foreach shape', { skip: !hasPowerShell() }, () => {
  const dir = mkdtempSync(join(tmpdir(), 'moor-offline-parse-'))
  try {
    const broken = join(dir, 'install.ps1')
    writeFileSync(broken, BROKEN_TIER_BLOCK)
    assert.throws(() => assertInstallPs1Parses(broken), /FAILED PowerShell parse/)
  } finally {
    rmSync(dir, { recursive: true, force: true })
  }
})

test('verifyOfflineBundle rejects a fresh-but-unparseable staged install.ps1', { skip: !hasPowerShell() }, () => {
  // Freshness checks pass (staged is byte-identical to source) but the file
  // itself cannot run — this is the .exe that died at `-Manifest` in the
  // field. The verify gate must refuse to ship it.
  const buildDir = mkdtempSync(join(tmpdir(), 'moor-offline-badparse-'))
  const repoRoot = mkdtempSync(join(tmpdir(), 'moor-offline-fakeroot-'))
  try {
    writeFileSync(join(buildDir, 'repo.zip'), Buffer.alloc(2 * 1024 * 1024))
    const scriptsDir = join(buildDir, 'offline-scripts')
    mkdirSync(scriptsDir, { recursive: true })
    writeFileSync(join(scriptsDir, 'install.ps1'), BROKEN_TIER_BLOCK)
    writeFileSync(join(scriptsDir, 'install.sh'), '#!/bin/sh\necho ok\n')
    const fakeScripts = join(repoRoot, 'scripts')
    mkdirSync(fakeScripts, { recursive: true })
    writeFileSync(join(fakeScripts, 'install.ps1'), BROKEN_TIER_BLOCK)
    writeFileSync(join(fakeScripts, 'install.sh'), '#!/bin/sh\necho ok\n')
    writeFileSync(join(repoRoot, 'pyproject.toml'), '[project]\nname = "moor"\n')
    writeFileSync(join(repoRoot, 'moor_bootstrap.py'), '# stub\n')
    writeFileSync(
      join(buildDir, 'install-stamp.json'),
      JSON.stringify({ schemaVersion: 1, commit: 'b'.repeat(40), branch: 'main' })
    )
    assert.throws(
      () => verifyOfflineBundle({ buildDir, repoRoot }),
      /FAILED PowerShell parse/
    )
  } finally {
    rmSync(buildDir, { recursive: true, force: true })
    rmSync(repoRoot, { recursive: true, force: true })
  }
})
