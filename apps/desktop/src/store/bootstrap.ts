import { atom } from 'nanostores'

import type { DesktopBootstrapEvent, DesktopBootstrapStageResult, DesktopBootstrapState, MoorConnection } from '@/global'
import { BACKEND_BOOT_WAIT_TIMEOUT_MS } from '@/lib/with-timeout'

export const EMPTY_BOOTSTRAP_STATE: DesktopBootstrapState = {
  active: false,
  manifest: null,
  stages: {},
  error: null,
  log: [],
  startedAt: null,
  completedAt: null,
  setupChoice: null,
  unsupportedPlatform: null
}

export function applyBootstrapEvent(
  state: DesktopBootstrapState,
  ev: DesktopBootstrapEvent
): DesktopBootstrapState {
  if (ev.type === 'dismissed') {
    return { ...EMPTY_BOOTSTRAP_STATE }
  }

  if (ev.type === 'setup-choice') {
    return {
      ...state,
      active: false,
      manifest: null,
      stages: {},
      error: null,
      setupChoice: ev.active
        ? {
            platform: ev.platform || state.setupChoice?.platform || 'unknown',
            activeRoot: ev.activeRoot || state.setupChoice?.activeRoot || ''
          }
        : null,
      unsupportedPlatform: null
    }
  }

  if (ev.type === 'manifest') {
    const stages: Record<string, DesktopBootstrapStageResult> = {}

    for (const stage of ev.stages) {
      stages[stage.name] = { state: 'pending', durationMs: null, startedAt: null, json: null, error: null }
    }

    return {
      ...state,
      active: true,
      manifest: { type: 'manifest', stages: ev.stages, protocolVersion: ev.protocolVersion },
      stages,
      error: null,
      setupChoice: null,
      startedAt: state.startedAt || Date.now()
    }
  }

  if (ev.type === 'stage') {
    const prev = state.stages[ev.name]

    return {
      ...state,
      stages: {
        ...state.stages,
        [ev.name]: {
          state: ev.state,
          durationMs: ev.durationMs ?? null,
          startedAt: ev.state === 'running' ? (prev?.startedAt ?? Date.now()) : (prev?.startedAt ?? null),
          json: ev.json ?? null,
          error: ev.error ?? null
        }
      }
    }
  }

  if (ev.type === 'log') {
    const next = state.log.concat({ ts: Date.now(), stage: ev.stage ?? null, line: ev.line, stream: ev.stream })

    while (next.length > 500) {
      next.shift()
    }

    return { ...state, log: next }
  }

  if (ev.type === 'complete') {
    return { ...state, active: false, completedAt: Date.now(), error: null }
  }

  if (ev.type === 'failed') {
    return { ...state, active: false, error: ev.error || 'unknown error', setupChoice: null }
  }

  if (ev.type === 'unsupported-platform') {
    return {
      ...state,
      active: false,
      setupChoice: null,
      unsupportedPlatform: {
        platform: ev.platform,
        activeRoot: ev.activeRoot,
        installCommand: ev.installCommand,
        docsUrl: ev.docsUrl
      }
    }
  }

  return state
}

export const $desktopBootstrap = atom<DesktopBootstrapState>(EMPTY_BOOTSTRAP_STATE)

export function isBootstrapActive(state: DesktopBootstrapState): boolean {
  return Boolean(state.active || state.setupChoice)
}

/**
 * Subscribes the shared $desktopBootstrap store to IPC bootstrap events and fetches
 * the initial snapshot on startup.
 */
export function initDesktopBootstrapListener(): () => void {
  const desktop = typeof window !== 'undefined' ? window.moorDesktop : undefined

  if (!desktop || typeof desktop.onBootstrapEvent !== 'function') {
    return () => undefined
  }

  let active = true

  if (typeof desktop.getBootstrapState === 'function') {
    void desktop
      .getBootstrapState()
      .then(snapshot => {
        if (active && snapshot) {
          $desktopBootstrap.set(snapshot)
        }
      })
      .catch(() => undefined)
  }

  const unsubscribe = desktop.onBootstrapEvent(ev => {
    if (!active) {
      return
    }

    $desktopBootstrap.set(applyBootstrapEvent($desktopBootstrap.get(), ev))
  })

  return () => {
    active = false
    unsubscribe()
  }
}

/**
 * Awaits a backend connection with bootstrap awareness:
 * - If bootstrap is active or streaming progress events, the timeout resets on every event so
 *   clean-install downloads and builds are not prematurely terminated.
 * - If first-run setup choice is pending user interaction, the timeout is suspended.
 * - The standard timeout only applies to periods of total inactivity.
 */
export async function waitForMoorConnectionWithBootstrap(
  getConnection: () => Promise<MoorConnection>,
  timeoutMs: number = BACKEND_BOOT_WAIT_TIMEOUT_MS
): Promise<MoorConnection> {
  return new Promise<MoorConnection>((resolve, reject) => {
    let settled = false
    let timer: ReturnType<typeof setTimeout> | null = null

    const clearInactivityTimer = () => {
      if (timer !== null) {
        clearTimeout(timer)
        timer = null
      }
    }

    const resetInactivityTimer = () => {
      if (settled) {
        return
      }

      clearInactivityTimer()

      const current = $desktopBootstrap.get()

      // While user is prompted for first-run setup choice, wait without an active countdown.
      if (current.setupChoice) {
        return
      }

      timer = setTimeout(() => {
        if (!settled) {
          settled = true
          unsubscribeBootstrap()
          reject(new Error('Timed out connecting to Moor backend'))
        }
      }, timeoutMs)
    }

    // Reset timer on any bootstrap state change / log / stage event
    const unsubscribeBootstrap = $desktopBootstrap.subscribe(() => {
      if (!settled) {
        resetInactivityTimer()
      }
    })

    resetInactivityTimer()

    getConnection()
      .then(conn => {
        if (!settled) {
          settled = true
          clearInactivityTimer()
          unsubscribeBootstrap()
          resolve(conn)
        }
      })
      .catch(err => {
        if (!settled) {
          settled = true
          clearInactivityTimer()
          unsubscribeBootstrap()
          reject(err)
        }
      })
  })
}
