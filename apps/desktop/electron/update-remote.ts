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

