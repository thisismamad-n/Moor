/**
 * Tests for electron/update-remote.ts — the remote-detection helpers that
 * keep passive update checks off the SSH origin for official installs.
 *
 * Run with: node --test electron/update-remote.test.ts
 * (Wired into npm test:desktop:platforms in package.json.)
 *
 * Why this matters: a public install can carry
 * origin=git@github.com:NousResearch/hermes-agent.git. A background
 * `git fetch origin` then authenticates over SSH and, with a FIDO2/passkey
 * key, triggers an unexplained hardware-touch prompt. isOfficialSshRemote
 * must reliably recognize the official SSH remote (in every URL form,
 * case-insensitively) so the caller can swap in the anonymous HTTPS path —
 * while NOT misclassifying forks, other hosts, or the HTTPS remote (which
 * never prompts and should keep the normal fetch path).
 */

import assert from 'node:assert/strict'

import { test } from 'vitest'

import {
  canonicalGitHubRemote,
  isOfficialSshRemote,
  isSshRemote,
  LEGACY_UPSTREAM_CANONICAL,
  OFFICIAL_REPO_CANONICAL,
  OFFICIAL_REPO_HTTPS_URL,
  resolveGitAuthArgs,
  resolveUpdateAuthHeaders
} from './update-remote'

test('canonicalGitHubRemote normalizes SSH and HTTPS forms for Moor and legacy upstream', () => {
  assert.equal(canonicalGitHubRemote('git@github.com:moor-inc/moor.git'), OFFICIAL_REPO_CANONICAL)
  assert.equal(canonicalGitHubRemote('git@github.com:moor-inc/moor'), OFFICIAL_REPO_CANONICAL)
  assert.equal(canonicalGitHubRemote('ssh://git@github.com/moor-inc/moor.git'), OFFICIAL_REPO_CANONICAL)
  assert.equal(canonicalGitHubRemote('https://github.com/moor-inc/moor.git'), OFFICIAL_REPO_CANONICAL)
  assert.equal(canonicalGitHubRemote('moor-inc/moor'), OFFICIAL_REPO_CANONICAL)

  assert.equal(canonicalGitHubRemote('git@github.com:NousResearch/hermes-agent.git'), LEGACY_UPSTREAM_CANONICAL)
  assert.equal(canonicalGitHubRemote('git@github.com:NousResearch/hermes-agent'), LEGACY_UPSTREAM_CANONICAL)
  assert.equal(canonicalGitHubRemote('ssh://git@github.com/NousResearch/hermes-agent.git'), LEGACY_UPSTREAM_CANONICAL)
  assert.equal(canonicalGitHubRemote('https://github.com/NousResearch/hermes-agent.git'), LEGACY_UPSTREAM_CANONICAL)
})

test('canonicalGitHubRemote is empty for falsy input', () => {
  assert.equal(canonicalGitHubRemote(''), '')
  assert.equal(canonicalGitHubRemote(null), '')
  assert.equal(canonicalGitHubRemote(undefined), '')
})

test('isSshRemote detects scp-like and ssh:// forms only', () => {
  assert.equal(isSshRemote('git@github.com:moor-inc/moor.git'), true)
  assert.equal(isSshRemote('ssh://git@github.com/moor-inc/moor.git'), true)
  assert.equal(isSshRemote('https://github.com/moor-inc/moor.git'), false)
  assert.equal(isSshRemote(''), false)
  assert.equal(isSshRemote(null), false)
})

test('isOfficialSshRemote is true for Moor repo and legacy upstream over SSH', () => {
  assert.equal(isOfficialSshRemote('git@github.com:moor-inc/moor.git'), true)
  assert.equal(isOfficialSshRemote('git@github.com:moor-inc/moor'), true)
  assert.equal(isOfficialSshRemote('ssh://git@github.com/moor-inc/moor.git'), true)

  assert.equal(isOfficialSshRemote('git@github.com:NousResearch/hermes-agent.git'), true)
  assert.equal(isOfficialSshRemote('git@github.com:NousResearch/hermes-agent'), true)
})

test('isOfficialSshRemote does NOT match unrelated forks, other hosts, or HTTPS', () => {
  assert.equal(isOfficialSshRemote('git@github.com:unrelated-user/random-repo.git'), false)
  assert.equal(isOfficialSshRemote('git@gitlab.com:moor-inc/moor.git'), false)
  assert.equal(isOfficialSshRemote('https://github.com/moor-inc/moor.git'), false)
  assert.equal(isOfficialSshRemote(''), false)
  assert.equal(isOfficialSshRemote(null), false)
})

test('OFFICIAL_REPO_HTTPS_URL canonicalizes to OFFICIAL_REPO_CANONICAL', () => {
  assert.equal(canonicalGitHubRemote(OFFICIAL_REPO_HTTPS_URL), OFFICIAL_REPO_CANONICAL)
})

test('resolveGitAuthArgs formats git extraHeader args when token is supplied', () => {
  assert.deepEqual(resolveGitAuthArgs(null), [])
  assert.deepEqual(resolveGitAuthArgs(''), [])
  assert.deepEqual(resolveGitAuthArgs('  '), [])
  assert.deepEqual(resolveGitAuthArgs('ghp_testToken123'), ['-c', 'http.extraHeader=AUTHORIZATION: bearer ghp_testToken123'])
})

test('resolveUpdateAuthHeaders creates headers with optional Bearer token', () => {
  const anon = resolveUpdateAuthHeaders(null)
  assert.equal(anon.Accept, 'application/vnd.github+json')
  assert.equal(anon['User-Agent'], 'moor-desktop-update-check')
  assert.equal(anon['Authorization'], undefined)

  const authed = resolveUpdateAuthHeaders('ghp_testToken123')
  assert.equal(authed['Authorization'], 'Bearer ghp_testToken123')
})

