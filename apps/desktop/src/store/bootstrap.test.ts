import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'

import type { DesktopBootstrapEvent, MoorConnection } from '@/global'

import {
  $desktopBootstrap,
  applyBootstrapEvent,
  EMPTY_BOOTSTRAP_STATE,
  initDesktopBootstrapListener,
  isBootstrapActive,
  waitForMoorConnectionWithBootstrap
} from './bootstrap'

describe('bootstrap store', () => {
  beforeEach(() => {
    vi.useFakeTimers()
    $desktopBootstrap.set(EMPTY_BOOTSTRAP_STATE)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    Reflect.deleteProperty(window, 'moorDesktop')
  })

  describe('applyBootstrapEvent', () => {
    it('handles manifest event', () => {
      const state = applyBootstrapEvent(EMPTY_BOOTSTRAP_STATE, {
        type: 'manifest',
        stages: [
          { name: 'uv', title: 'Install uv', category: 'prereqs', needs_user_input: false },
          { name: 'git', title: 'Install git', category: 'prereqs', needs_user_input: false }
        ],
        protocolVersion: 1
      })

      expect(state.active).toBe(true)
      expect(state.manifest?.stages).toHaveLength(2)
      expect(state.stages.uv?.state).toBe('pending')
      expect(state.stages.git?.state).toBe('pending')
      expect(typeof state.startedAt).toBe('number')
    })

    it('handles stage event', () => {
      const manifestState = applyBootstrapEvent(EMPTY_BOOTSTRAP_STATE, {
        type: 'manifest',
        stages: [{ name: 'uv', title: 'Install uv', category: 'prereqs', needs_user_input: false }],
        protocolVersion: 1
      })

      const runningState = applyBootstrapEvent(manifestState, {
        type: 'stage',
        name: 'uv',
        state: 'running'
      })
      expect(runningState.stages.uv?.state).toBe('running')
      expect(typeof runningState.stages.uv?.startedAt).toBe('number')

      const successState = applyBootstrapEvent(runningState, {
        type: 'stage',
        name: 'uv',
        state: 'succeeded',
        durationMs: 1200
      })
      expect(successState.stages.uv?.state).toBe('succeeded')
      expect(successState.stages.uv?.durationMs).toBe(1200)
    })

    it('handles log event with ring buffer limit', () => {
      let state = EMPTY_BOOTSTRAP_STATE
      for (let i = 0; i < 550; i += 1) {
        state = applyBootstrapEvent(state, {
          type: 'log',
          stage: 'uv',
          line: `log line ${i}`,
          stream: 'stdout'
        })
      }

      expect(state.log).toHaveLength(500)
      expect(state.log[state.log.length - 1]?.line).toBe('log line 549')
    })

    it('handles complete and failed events', () => {
      const activeState = applyBootstrapEvent(EMPTY_BOOTSTRAP_STATE, {
        type: 'manifest',
        stages: [],
        protocolVersion: 1
      })

      const failedState = applyBootstrapEvent(activeState, {
        type: 'failed',
        error: 'uv failed'
      })
      expect(failedState.active).toBe(false)
      expect(failedState.error).toBe('uv failed')

      const completedState = applyBootstrapEvent(activeState, {
        type: 'complete',
        marker: { version: 1 }
      })
      expect(completedState.active).toBe(false)
      expect(completedState.error).toBeNull()
      expect(typeof completedState.completedAt).toBe('number')
    })

    it('handles setup-choice and dismissed events', () => {
      const choiceState = applyBootstrapEvent(EMPTY_BOOTSTRAP_STATE, {
        type: 'setup-choice',
        active: true,
        platform: 'win32',
        activeRoot: 'C:\\Moor'
      })
      expect(choiceState.setupChoice).toEqual({
        platform: 'win32',
        activeRoot: 'C:\\Moor',
        local: 'none',
        bundled: false
      })

      const dismissedState = applyBootstrapEvent(choiceState, { type: 'dismissed' })
      expect(dismissedState).toEqual(EMPTY_BOOTSTRAP_STATE)
    })
  })

  describe('isBootstrapActive', () => {
    it('identifies when bootstrap is active or setup choice is open', () => {
      expect(isBootstrapActive(EMPTY_BOOTSTRAP_STATE)).toBe(false)

      expect(isBootstrapActive({ ...EMPTY_BOOTSTRAP_STATE, active: true })).toBe(true)

      expect(
        isBootstrapActive({
          ...EMPTY_BOOTSTRAP_STATE,
          setupChoice: { platform: 'win32', activeRoot: 'C:\\Moor', local: 'none', bundled: false }
        })
      ).toBe(true)
    })
  })

  describe('initDesktopBootstrapListener', () => {
    it('subscribes to window.moorDesktop events and loads snapshot', async () => {
      let listener: ((ev: DesktopBootstrapEvent) => void) | null = null
      const unsubscribe = vi.fn()

      Object.defineProperty(window, 'moorDesktop', {
        configurable: true,
        value: {
          getBootstrapState: vi.fn().mockResolvedValue({
            ...EMPTY_BOOTSTRAP_STATE,
            active: true
          }),
          onBootstrapEvent: vi.fn((cb: (ev: DesktopBootstrapEvent) => void) => {
            listener = cb
            return unsubscribe
          })
        }
      })

      const cleanup = initDesktopBootstrapListener()
      await Promise.resolve()

      expect($desktopBootstrap.get().active).toBe(true)

      const emit = listener as ((ev: DesktopBootstrapEvent) => void) | null
      emit?.({
        type: 'failed',
        error: 'Install error'
      })
      expect($desktopBootstrap.get().error).toBe('Install error')

      cleanup()
      expect(unsubscribe).toHaveBeenCalled()
    })
  })

  describe('waitForMoorConnectionWithBootstrap', () => {
    const mockConn = { kind: 'local', port: 9191 } as unknown as MoorConnection

    it('resolves immediately when getConnection succeeds', async () => {
      const promise = waitForMoorConnectionWithBootstrap(async () => mockConn, 5000)
      await expect(promise).resolves.toBe(mockConn)
    })

    it('rejects when getConnection rejects', async () => {
      const promise = waitForMoorConnectionWithBootstrap(async () => {
        throw new Error('Connection refused')
      }, 5000)
      await expect(promise).rejects.toThrow('Connection refused')
    })

    it('times out after timeoutMs when no progress occurs', async () => {
      const promise = waitForMoorConnectionWithBootstrap(
        () => new Promise<MoorConnection>(() => undefined),
        5000
      )

      vi.advanceTimersByTime(5001)
      await expect(promise).rejects.toThrow('Timed out connecting to Moor backend')
    })

    it('resets timeout when bootstrap events stream in', async () => {
      const deferredPromise = new Promise<MoorConnection>(resolve => {
        setTimeout(() => resolve(mockConn), 8000)
      })

      const waitPromise = waitForMoorConnectionWithBootstrap(() => deferredPromise, 5000)

      // At 4 seconds, an event streams in (timer resets for another 5s)
      vi.advanceTimersByTime(4000)
      $desktopBootstrap.set(
        applyBootstrapEvent($desktopBootstrap.get(), {
          type: 'log',
          stage: 'uv',
          line: 'downloading uv...',
          stream: 'stdout'
        })
      )

      // Advance another 3 seconds (total elapsed 7s, but only 3s since last event)
      vi.advanceTimersByTime(3000)

      // At 7 seconds, another event arrives
      $desktopBootstrap.set(
        applyBootstrapEvent($desktopBootstrap.get(), {
          type: 'stage',
          name: 'uv',
          state: 'succeeded'
        })
      )

      // Advance remaining time for deferredPromise to resolve (total 8s)
      vi.advanceTimersByTime(1000)

      await expect(waitPromise).resolves.toBe(mockConn)
    })

    it('suspends timeout countdown while setup-choice is pending', async () => {
      $desktopBootstrap.set({
        ...EMPTY_BOOTSTRAP_STATE,
        setupChoice: { platform: 'win32', activeRoot: 'C:\\Moor', local: 'none', bundled: false }
      })

      let resolveConn: (c: MoorConnection) => void
      const connPromise = new Promise<MoorConnection>(resolve => {
        resolveConn = resolve
      })

      const waitPromise = waitForMoorConnectionWithBootstrap(() => connPromise, 5000)

      // Advance well past 5000ms while user is deciding setupChoice
      vi.advanceTimersByTime(60_000)

      // User picks choice and connection establishes
      $desktopBootstrap.set({
        ...EMPTY_BOOTSTRAP_STATE,
        setupChoice: null,
        active: true
      })

      resolveConn!(mockConn)
      await expect(waitPromise).resolves.toBe(mockConn)
    })
  })
})
