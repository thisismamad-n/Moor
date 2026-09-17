/**
 * Pure helpers for choosing a remote URL during passive update checks.
 *
 * A public install can end up with `origin=git@github.com:NousResearch/hermes-agent.git`.
 * If the user's GitHub SSH key is FIDO2/passkey-backed, a background `git fetch
 * origin` triggers an unexplained hardware-touch prompt. For passive checks
 * against the official repo we substitute the public HTTPS `ls-remote` path,
 * which needs no auth and cannot prompt. Active update/apply flows are left
 * unchanged.
 *
 * Extracted from main.ts so the security-critical remote detection is unit
 * testable without booting Electron (main.ts requires('electron') at load).
 */

const OFFICIAL_REPO_HTTPS_URL = 'https://github.com/moor-inc/moor.git'
const OFFICIAL_REPO_CANONICAL = 'github.com/moor-inc/moor'
const LEGACY_UPSTREAM_CANONICAL = 'github.com/nousresearch/hermes-agent'

// Normalize common GitHub remote URL forms to `host/owner/repo` (lowercased,
// no trailing slash, no .git suffix) so SSH and HTTPS forms of the same repo
// compare equal.
function canonicalGitHubRemote(url) {
  if (!url) {
    return ''
  }

  let value = String(url).trim()

  if (value.startsWith('git@github.com:')) {
    value = `github.com/${value.slice('git@github.com:'.length)}`
  } else if (value.startsWith('ssh://git@github.com/')) {
    value = `github.com/${value.slice('ssh://git@github.com/'.length)}`
  } else {
    try {
      const parsed = new URL(value)

      if (parsed.hostname && parsed.pathname) {
        value = `${parsed.hostname}${parsed.pathname}`
      }
    } catch {
      // If given owner/repo directly without scheme
      if (/^[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+$/.test(value)) {
        value = `github.com/${value}`
      }
    }
  }

  value = value.trim().replace(/\/+$/, '')

  if (value.endsWith('.git')) {
    value = value.slice(0, -4)
  }

  return value.toLowerCase()
}

function isSshRemote(url) {
  const value = String(url || '')
    .trim()
    .toLowerCase()

  return value.startsWith('git@') || value.startsWith('ssh://')
}

function isOfficialSshRemote(url?: string | null, customCanonical?: string | null): boolean {
  const canonical = canonicalGitHubRemote(url)
  const official = customCanonical ? String(customCanonical).toLowerCase() : OFFICIAL_REPO_CANONICAL

  return isSshRemote(url) && (canonical === official || canonical === LEGACY_UPSTREAM_CANONICAL || canonical === OFFICIAL_REPO_CANONICAL)
}

export function resolveMoorUpdateSource(repo?: string, branch?: string) {
  const source = { repo: 'thisismamad-n/Moor', branch: 'master', url: 'https://github.com/thisismamad-n/Moor.git' }
  if (repo && canonicalGitHubRemote(repo) !== canonicalGitHubRemote(source.url)) {
    throw new Error('Updates must use thisismamad-n/Moor. Configure the Moor repository in Settings → About.')
  }
  if (branch && branch !== source.branch) {
    throw new Error('Moor updates are published on master. Select master before updating.')
  }
  return source
}

export function resolveMoorUpdateEnv(token?: string, base: NodeJS.ProcessEnv = process.env): NodeJS.ProcessEnv {
  const clean = (token || base.MOOR_GITHUB_TOKEN || base.GITHUB_TOKEN || base.GH_TOKEN || '').trim()
  if (/[\r\n\0]/.test(clean)) throw new Error('Invalid update token.')
  const env: NodeJS.ProcessEnv = { ...base, GIT_TERMINAL_PROMPT: '0', GCM_INTERACTIVE: 'Never' }
  if (!clean) return env
  const count = Number(env.GIT_CONFIG_COUNT || 0)
  if (!Number.isSafeInteger(count) || count < 0) throw new Error('Invalid Git environment configuration.')
  return {
    ...env,
    MOOR_GITHUB_TOKEN: clean,
    GIT_CONFIG_COUNT: String(count + 1),
    [`GIT_CONFIG_KEY_${count}`]: `http.${resolveMoorUpdateSource().url}.extraHeader`,
    [`GIT_CONFIG_VALUE_${count}`]: `Authorization: Basic ${Buffer.from(`x-access-token:${clean}`).toString('base64')}`
  }
}

function resolveGitAuthArgs(token?: string | null): string[] {
  const clean = String(token || '').trim()
  if (!clean) {
    return []
  }

  return ['-c', `http.extraHeader=AUTHORIZATION: bearer ${clean}`]
}

function resolveUpdateAuthHeaders(token?: string | null): Record<string, string> {
  const headers: Record<string, string> = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'moor-desktop-update-check'
  }

  const clean = String(token || '').trim()
  if (clean) {
    headers.Authorization = `Bearer ${clean}`
  }

  return headers
}

export {
  canonicalGitHubRemote,
  isOfficialSshRemote,
  isSshRemote,
  LEGACY_UPSTREAM_CANONICAL,
  OFFICIAL_REPO_CANONICAL,
  OFFICIAL_REPO_HTTPS_URL,
  resolveGitAuthArgs,
  resolveUpdateAuthHeaders
}

