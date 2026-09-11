import assert from 'node:assert/strict'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import { test } from 'vitest'

import {
  buildPinArgs,
  buildPosixPinArgs,
  cachedScriptPath,
  hasExistingGitCheckout,
  installedAgentInstallScript,
  installRefForStamp,
  installScriptUrl,
  isPinnedCommit,
  resolveBundledInstallScript,
  resolveInstallScript,
  resolveInstallScriptRepo,
  resolveMarkerPinnedCommit,
  runBootstrap,
  UPSTREAM_INSTALL_REPO
} from './bootstrap-runner'

const SCRIPT_NAME = process.platform === 'win32' ? 'install.ps1' : 'install.sh'
const ZERO_COMMIT = '0000000000000000000000000000000000000000'

function mkTmpHome() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'moor-bootstrap-test-'))
}

test('runBootstrap bails immediately when the signal is already aborted', async () => {
  const controller = new AbortController()
  controller.abort()

  const events = []

  const result = await runBootstrap({
    installStamp: null,
    activeRoot: '/tmp/moor-runner-test',
    sourceRepoRoot: null,
    moorHome: '/tmp/moor-runner-test',
    logRoot: '/tmp/moor-runner-test',
    onEvent: ev => events.push(ev),
    abortSignal: controller.signal
  })

  // Cancelled before any install script is spawned.
  assert.deepEqual(result, { ok: false, cancelled: true })
  assert.ok(
    events.some(ev => ev.type === 'failed' && /cancelled/i.test(ev.error)),
    'should emit a cancelled failure event'
  )
})

test('installedAgentInstallScript resolves the installer in the agent checkout', () => {
  const home = mkTmpHome()

  try {
    assert.equal(installedAgentInstallScript(home), null, 'absent before the checkout exists')

    const scriptsDir = path.join(home, 'moor-agent', 'scripts')
    fs.mkdirSync(scriptsDir, { recursive: true })
    const scriptPath = path.join(scriptsDir, SCRIPT_NAME)
    fs.writeFileSync(scriptPath, '#!/bin/sh\necho hi\n')

    assert.equal(installedAgentInstallScript(home), scriptPath)
    assert.equal(installedAgentInstallScript(null), null, 'null home -> null')
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
})

test('existing checkout detection requires git metadata', () => {
  const home = mkTmpHome()

  try {
    const activeRoot = path.join(home, 'moor-agent')
    assert.equal(hasExistingGitCheckout(activeRoot), false)

    fs.mkdirSync(path.join(activeRoot, '.git'), { recursive: true })
    assert.equal(hasExistingGitCheckout(activeRoot), true)
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
})

test('fresh bootstrap args include the packaged commit pin', () => {
  const installStamp = { commit: 'a'.repeat(40), branch: 'main' }

  assert.deepEqual(buildPinArgs(installStamp), ['-Commit', installStamp.commit, '-Branch', 'main'])
  assert.deepEqual(
    buildPosixPinArgs({
      installStamp,
      activeRoot: '/tmp/moor-agent',
      moorHome: '/tmp/moor'
    }),
    ['--dir', '/tmp/moor-agent', '--moor-home', '/tmp/moor', '--branch', 'main', '--commit', installStamp.commit]
  )
})

test('existing-checkout bootstrap args keep branch but skip the packaged commit pin', () => {
  const installStamp = { commit: 'a'.repeat(40), branch: 'main' }

  assert.deepEqual(buildPinArgs(installStamp, { pinCommit: false }), ['-Branch', 'main'])
  assert.deepEqual(
    buildPosixPinArgs({
      installStamp,
      activeRoot: '/tmp/moor-agent',
      moorHome: '/tmp/moor',
      pinCommit: false
    }),
    ['--dir', '/tmp/moor-agent', '--moor-home', '/tmp/moor', '--branch', 'main']
  )
})

test('fallback install stamps use an unpinned branch ref', () => {
  const stamp = { commit: ZERO_COMMIT, branch: 'main' }

  assert.equal(isPinnedCommit(ZERO_COMMIT), false)
  assert.deepEqual(installRefForStamp(stamp), {
    ref: 'main',
    cacheKey: 'fallback-main',
    pinned: false
  })
  // Must NOT pass -Commit / --commit for the all-zero placeholder.
  assert.deepEqual(buildPinArgs(stamp), ['-Branch', 'main'])
  assert.deepEqual(
    buildPosixPinArgs({
      installStamp: stamp,
      activeRoot: '/tmp/moor',
      moorHome: '/tmp/home'
    }),
    ['--dir', '/tmp/moor', '--moor-home', '/tmp/home', '--branch', 'main']
  )
})

test('resolveMarkerPinnedCommit prefers real HEAD over fallback stamp zeros', () => {
  const realHead = 'c'.repeat(40)
  assert.equal(
    resolveMarkerPinnedCommit({ commit: ZERO_COMMIT, branch: 'main' }, '/tmp/checkout', {
      resolveHead: () => realHead
    }),
    realHead
  )
  assert.equal(
    resolveMarkerPinnedCommit({ commit: 'd'.repeat(40), branch: 'main' }, '/tmp/checkout', {
      resolveHead: () => realHead
    }),
    'd'.repeat(40),
    'packaged real pin wins over checkout HEAD'
  )
  assert.equal(
    resolveMarkerPinnedCommit({ commit: ZERO_COMMIT, branch: 'main' }, '/tmp/missing', {
      resolveHead: () => null
    }),
    null
  )
})

test('resolveInstallScript downloads fallback stamps by branch instead of zero commit', async () => {
  const home = mkTmpHome()

  try {
    const logs = []
    const refs = []

    const result = await resolveInstallScript({
      installStamp: { commit: ZERO_COMMIT, branch: 'main' },
      sourceRepoRoot: null,
      moorHome: home,
      emit: ev => logs.push(ev),
      _download: async (ref, destPath) => {
        refs.push(ref)
        fs.mkdirSync(path.dirname(destPath), { recursive: true })
        fs.writeFileSync(destPath, '#!/bin/sh\necho fallback branch\n')

        return destPath
      }
    })

    assert.deepEqual(refs, ['main'])
    assert.equal(result.source, 'download')
    assert.equal(result.commit, null)
    assert.equal(result.path, cachedScriptPath(home, 'fallback-main'))
    assert.ok(
      logs.some(ev => /fallback, unpinned/.test(ev.line || '')),
      'emits an unpinned fallback log line'
    )
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
})

test('resolveInstallScript prefers a cached script without touching the network', async () => {
  const home = mkTmpHome()

  try {
    const commit = 'a'.repeat(40)
    const cached = cachedScriptPath(home, commit)
    fs.mkdirSync(path.dirname(cached), { recursive: true })
    fs.writeFileSync(cached, '#!/bin/sh\necho cached\n')

    const logs = []

    const result = await resolveInstallScript({
      installStamp: { commit },
      sourceRepoRoot: null,
      moorHome: home,
      emit: ev => logs.push(ev)
    })

    assert.equal(result.source, 'cache')
    assert.equal(result.path, cached)
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
})

test('resolveInstallScript falls back to the installed agent checkout on a 404', async () => {
  const home = mkTmpHome()

  try {
    const commit = 'a'.repeat(40)
    // Seed the installed agent checkout so the fallback has something to resolve.
    const scriptsDir = path.join(home, 'moor-agent', 'scripts')
    fs.mkdirSync(scriptsDir, { recursive: true })
    const installed = path.join(scriptsDir, SCRIPT_NAME)
    fs.writeFileSync(installed, '#!/bin/sh\necho fallback\n')

    const logs = []

    const result = await resolveInstallScript({
      installStamp: { commit },
      sourceRepoRoot: null,
      moorHome: home,
      emit: ev => logs.push(ev),
      // Simulate GitHub returning a 404 for the pinned commit.
      _download: async () => {
        throw new Error('Failed to download install.sh: HTTP 404')
      }
    })

    assert.equal(result.source, 'installed-agent')
    // It should have copied the installer into the bootstrap cache.
    assert.equal(result.path, cachedScriptPath(home, commit))
    assert.ok(fs.existsSync(result.path), 'fallback script copied into cache')
    assert.ok(
      logs.some(ev => /falling back to installed agent/.test(ev.line || '')),
      'emits a fallback log line'
    )
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
})

test('resolveInstallScript rethrows when the 404 fallback is unavailable', async () => {
  const home = mkTmpHome()

  try {
    const commit = 'a'.repeat(40)
    // No installed agent checkout seeded -> nothing to fall back to.
    await assert.rejects(
      resolveInstallScript({
        installStamp: { commit },
        sourceRepoRoot: null,
        moorHome: home,
        emit: () => {},
        _bundled: () => null,
        _download: async () => {
          throw new Error('Failed to download install.sh: HTTP 404')
        }
      }),
      /HTTP 404|Failed to download/
    )
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
})

test('resolveInstallScript prefers bundled install script when available', async () => {
  const home = mkTmpHome()

  try {
    const logs: any[] = []
    const dummyBundledPath = path.join(home, SCRIPT_NAME)
    fs.writeFileSync(dummyBundledPath, '#!/bin/sh\necho bundled\n')

    const result = await resolveInstallScript({
      installStamp: { commit: 'a'.repeat(40) },
      sourceRepoRoot: null,
      moorHome: home,
      emit: ev => logs.push(ev),
      _bundled: () => dummyBundledPath
    })

    assert.equal(result.source, 'bundled')
    assert.equal(result.path, dummyBundledPath)
    assert.ok(logs.some(ev => /using bundled/.test(ev.line || '')))
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
})

test('resolveBundledInstallScript resolves valid custom or resources path', () => {
  const home = mkTmpHome()

  try {
    const scriptPath = path.join(home, SCRIPT_NAME)
    fs.writeFileSync(scriptPath, '#!/bin/sh\necho test\n')

    assert.equal(resolveBundledInstallScript(scriptPath), scriptPath)
    assert.equal(resolveBundledInstallScript('/nonexistent/path/here'), null)
  } finally {
    fs.rmSync(home, { recursive: true, force: true })
  }
})

test('resolveInstallScriptRepo prefers the stamp repo, then env, then upstream', () => {
  const savedRepo = process.env.MOOR_GITHUB_REPO
  const savedFork = process.env.MOOR_GITHUB_FORK

  try {
    delete process.env.MOOR_GITHUB_REPO
    delete process.env.MOOR_GITHUB_FORK

    // Packaged Moor builds bake their own slug into install-stamp.json.
    assert.equal(
      resolveInstallScriptRepo({ commit: 'a'.repeat(40), branch: 'main', repo: 'moor-inc/moor' }),
      'moor-inc/moor'
    )
    // Legacy stamps without a repo field keep the old behaviour.
    assert.equal(resolveInstallScriptRepo({ commit: 'a'.repeat(40) }), UPSTREAM_INSTALL_REPO)
    assert.equal(resolveInstallScriptRepo(null), UPSTREAM_INSTALL_REPO)

    // Explicit runtime override beats the default (private Moor forks).
    process.env.MOOR_GITHUB_REPO = 'moor-inc/moor-private'
    assert.equal(resolveInstallScriptRepo(null), 'moor-inc/moor-private')

    // ...but never the baked stamp.
    delete process.env.MOOR_GITHUB_REPO
    process.env.MOOR_GITHUB_FORK = 'moor-inc/moor-fork'
    assert.equal(
      resolveInstallScriptRepo({ commit: 'a'.repeat(40), repo: 'moor-inc/moor' }),
      'moor-inc/moor'
    )
  } finally {
    if (savedRepo === undefined) {
      delete process.env.MOOR_GITHUB_REPO
    } else {
      process.env.MOOR_GITHUB_REPO = savedRepo
    }
    if (savedFork === undefined) {
      delete process.env.MOOR_GITHUB_FORK
    } else {
      process.env.MOOR_GITHUB_FORK = savedFork
    }
  }
})

test('installScriptUrl carries the resolved repo slug, not a hardcoded one', () => {
  const savedRepo = process.env.MOOR_GITHUB_REPO
  const savedFork = process.env.MOOR_GITHUB_FORK

  try {
    delete process.env.MOOR_GITHUB_REPO
    delete process.env.MOOR_GITHUB_FORK

    const commit = 'd'.repeat(40)
    assert.equal(
      installScriptUrl(commit, 'install.ps1', { commit, repo: 'moor-inc/moor' }),
      `https://raw.githubusercontent.com/moor-inc/moor/${commit}/scripts/install.ps1`
    )
    assert.equal(
      installScriptUrl('main', 'install.sh', null),
      `https://raw.githubusercontent.com/${UPSTREAM_INSTALL_REPO}/main/scripts/install.sh`
    )
  } finally {
    if (savedRepo === undefined) {
      delete process.env.MOOR_GITHUB_REPO
    } else {
      process.env.MOOR_GITHUB_REPO = savedRepo
    }
    if (savedFork === undefined) {
      delete process.env.MOOR_GITHUB_FORK
    } else {
      process.env.MOOR_GITHUB_FORK = savedFork
    }
  }
})
