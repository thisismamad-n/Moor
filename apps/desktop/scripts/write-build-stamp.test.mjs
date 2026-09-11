import assert from 'node:assert/strict'
import { test } from 'vitest'

import {
  FALLBACK_BRANCH,
  FALLBACK_COMMIT,
  fromCI,
  fromFallback,
  fromLocalGit,
  isFallbackCommit,
  parseRepoSlug,
  resolveRepoSlug,
  resolveStamp,
  UPSTREAM_REPO
} from './write-build-stamp.mjs'

test('fromCI reads GITHUB_SHA / GITHUB_REF_NAME', () => {
  assert.deepEqual(
    fromCI({ GITHUB_SHA: 'a'.repeat(40), GITHUB_REF_NAME: 'release' }),
    { commit: 'a'.repeat(40), branch: 'release', dirty: false, source: 'ci' }
  )
  assert.equal(fromCI({}), null)
})

test('fromLocalGit returns null when git rev-parse fails', () => {
  const stamp = fromLocalGit('/tmp/not-a-repo', () => null)
  assert.equal(stamp, null)
})

test('fromLocalGit reads HEAD + branch + dirty status', () => {
  const calls = []
  const execFn = (cmd) => {
    calls.push(cmd)
    if (cmd === 'git rev-parse HEAD') return 'b'.repeat(40)
    if (cmd === 'git rev-parse --abbrev-ref HEAD') return 'main'
    if (cmd === 'git status --porcelain -uno') return ' M apps/desktop/package.json'
    return null
  }
  assert.deepEqual(fromLocalGit('/repo', execFn), {
    commit: 'b'.repeat(40),
    branch: 'main',
    dirty: true,
    source: 'local'
  })
  assert.ok(calls.includes('git rev-parse HEAD'))
})

test('fromFallback uses the all-zero placeholder commit', () => {
  assert.deepEqual(fromFallback(), {
    commit: FALLBACK_COMMIT,
    branch: FALLBACK_BRANCH,
    dirty: false,
    source: 'fallback'
  })
  assert.equal(isFallbackCommit(FALLBACK_COMMIT), true)
  assert.equal(isFallbackCommit('a'.repeat(40)), false)
})

test('resolveStamp prefers CI over local git over fallback', () => {
  const ci = resolveStamp({
    env: { GITHUB_SHA: 'c'.repeat(40), GITHUB_REF_NAME: 'main' },
    execFn: () => 'should-not-run'
  })
  assert.equal(ci.source, 'ci')
  assert.equal(ci.commit, 'c'.repeat(40))

  const local = resolveStamp({
    env: {},
    execFn: (cmd) => {
      if (cmd === 'git rev-parse HEAD') return 'd'.repeat(40)
      if (cmd === 'git rev-parse --abbrev-ref HEAD') return 'main'
      if (cmd === 'git status --porcelain -uno') return ''
      return null
    }
  })
  assert.equal(local.source, 'local')
  assert.equal(local.commit, 'd'.repeat(40))
  assert.equal(local.dirty, false)
})

test('resolveStamp falls back when neither CI nor git is available', () => {
  const stamp = resolveStamp({ env: {}, execFn: () => null })
  assert.deepEqual(stamp, {
    commit: FALLBACK_COMMIT,
    branch: FALLBACK_BRANCH,
    dirty: false,
    source: 'fallback',
    repo: UPSTREAM_REPO
  })
})

test('parseRepoSlug handles https, ssh, and ssh-url remotes', () => {
  assert.equal(parseRepoSlug('https://github.com/moor-inc/moor.git'), 'moor-inc/moor')
  assert.equal(parseRepoSlug('https://github.com/NousResearch/hermes-agent'), 'NousResearch/hermes-agent')
  assert.equal(parseRepoSlug('git@github.com:moor-inc/moor.git'), 'moor-inc/moor')
  assert.equal(parseRepoSlug('ssh://git@github.com/moor-inc/moor.git'), 'moor-inc/moor')
  assert.equal(parseRepoSlug('not-a-remote'), null)
  assert.equal(parseRepoSlug(''), null)
})

test('resolveRepoSlug prefers explicit Moor override over CI over origin', () => {
  const noGit = () => null
  assert.equal(
    resolveRepoSlug({ env: { MOOR_GITHUB_REPO: 'moor-inc/moor' }, execFn: noGit }),
    'moor-inc/moor'
  )
  assert.equal(
    resolveRepoSlug({ env: { MOOR_GITHUB_FORK: 'moor-inc/moor' }, execFn: noGit }),
    'moor-inc/moor'
  )
  assert.equal(
    resolveRepoSlug({ env: { GITHUB_REPOSITORY: 'moor-inc/moor' }, execFn: noGit }),
    'moor-inc/moor'
  )
  assert.equal(
    resolveRepoSlug({
      env: {},
      execFn: cmd => (cmd === 'git remote get-url origin' ? 'git@github.com:moor-inc/moor.git' : null)
    }),
    'moor-inc/moor'
  )
  assert.equal(resolveRepoSlug({ env: {}, execFn: noGit }), UPSTREAM_REPO)
})
