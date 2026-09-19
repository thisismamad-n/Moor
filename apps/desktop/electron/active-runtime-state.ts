export interface BootstrapMarkerLike {
  pinnedCommit?: unknown
  schemaVersion?: unknown
  pinnedBranch?: unknown
  completedAt?: unknown
  desktopVersion?: unknown
}

export interface ActiveRuntimeStampLike {
  commit?: string | null
  branch?: string | null
  builtAt?: string | null
  source?: string | null
}

export interface ActiveRuntimeOptions {
  isPackaged?: boolean
  installStamp?: ActiveRuntimeStampLike | null
  activeCommit?: string | null
  activeIsAhead?: boolean
}

export interface ActiveRuntimeState {
  hasValidMarker: boolean
  shouldUseActiveRuntime: boolean
  usabilityReason: 'usable' | 'unusable' | 'upgrade-needed'
}

export function isRealCommitSha(commit: unknown): commit is string {
  if (typeof commit !== 'string') {
    return false
  }

  const trimmed = commit.trim()

  if (trimmed.length < 7 || trimmed.length > 64) {
    return false
  }

  if (/^0+$/.test(trimmed)) {
    return false
  }

  return /^[0-9a-fA-F]+$/.test(trimmed)
}

export function hasValidBootstrapMarker(
  marker: BootstrapMarkerLike | null | undefined,
  schemaVersion: number
): boolean {
  if (!marker || typeof marker !== 'object') {
    return false
  }

  if (marker.schemaVersion !== schemaVersion) {
    return false
  }

  if (!isRealCommitSha(marker.pinnedCommit)) {
    return false
  }

  return true
}

// The active install at ~/.moor/moor-agent can be real and runnable even if
// Desktop never wrote its first-run bootstrap marker (for example when Moor
// was installed by the CLI first, or when a past desktop build forgot the
// marker). Runtime usability is authoritative for "can we launch local Moor
// right now?"; the marker is provenance about how that install was created.
//
// In a packaged desktop release, however, the app ships with a specific
// installStamp commit and bundled repo.zip. If the active runtime at
// ACTIVE_MOOR_ROOT belongs to an older/stale commit and is not ahead, we must
// not run an outdated, incompatible backend. Marking it 'upgrade-needed'
// routes to the bootstrap runner to update from repo.zip seamlessly.
export function classifyActiveRuntime(
  marker: BootstrapMarkerLike | null | undefined,
  schemaVersion: number,
  runtimeUsable: boolean,
  options?: ActiveRuntimeOptions
): ActiveRuntimeState {
  const hasValidMarker = hasValidBootstrapMarker(marker, schemaVersion)

  if (!runtimeUsable) {
    return {
      hasValidMarker,
      shouldUseActiveRuntime: false,
      usabilityReason: 'unusable'
    }
  }

  if (options?.isPackaged && isRealCommitSha(options.installStamp?.commit)) {
    const packagedCommit = options.installStamp.commit.trim().toLowerCase()
    const markerCommit = typeof marker?.pinnedCommit === 'string' ? marker.pinnedCommit.trim().toLowerCase() : null
    const activeCommit = typeof options.activeCommit === 'string' ? options.activeCommit.trim().toLowerCase() : null

    const matchesPackaged =
      (markerCommit !== null && markerCommit === packagedCommit) ||
      (activeCommit !== null && activeCommit === packagedCommit)

    if (!matchesPackaged && !options.activeIsAhead) {
      return {
        hasValidMarker,
        shouldUseActiveRuntime: false,
        usabilityReason: 'upgrade-needed'
      }
    }
  }

  return {
    hasValidMarker,
    shouldUseActiveRuntime: true,
    usabilityReason: 'usable'
  }
}

