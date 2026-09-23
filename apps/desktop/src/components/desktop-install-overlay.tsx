import { useEffect, useMemo, useRef, useState } from 'react'

import { BrandMark } from '@/components/brand-mark'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { ErrorIcon } from '@/components/ui/error-state'
import { Loader } from '@/components/ui/loader'
import { LogView } from '@/components/ui/log-view'
import { Progress } from '@/components/ui/progress'
import type {
  DesktopBootstrapEvent,
  DesktopBootstrapStageDescriptor,
  DesktopBootstrapStageResult,
  DesktopBootstrapStageState,
  DesktopBootstrapState
} from '@/global'
import { useI18n } from '@/i18n'
import { AlertCircle, ChevronDown, ChevronRight, Globe, iconSize, Loader2, Monitor } from '@/lib/icons'
import { capitalize } from '@/lib/text'
import { cn } from '@/lib/utils'

import { FirstRunRemoteForm } from './first-run-remote-form'

/**
 * DesktopInstallOverlay
 *
 * Renders the first-launch install progress for Moor Agent. Mounted always;
 * shows itself only when main.ts reports an in-flight bootstrap (state.active)
 * OR an error from a completed-failed bootstrap (state.error). When the
 * bootstrap finishes successfully the overlay fades out and the rest of the
 * app (existing onboarding overlay -> main UI) takes over.
 *
 * Subscribes to two channels:
 *   - getBootstrapState()           -- initial snapshot on mount
 *   - onBootstrapEvent(callback)    -- live event stream
 *
 * The reducer is intentionally simple: every event mutates an in-component
 * snapshot the same way main.ts mutates its server-side snapshot. We don't
 * try to reconcile -- if we miss an event (shouldn't happen) the initial
 * getBootstrapState() call will resync the picture on the next render.
 *
 * Stages flagged needs_user_input render with a deliberately subdued style:
 * they're expected to come back as skipped=true (install.ps1 short-circuits
 * them under -NonInteractive). The post-install configuration flow that
 * those stages cover (API key, model, persona, gateway autostart) is handled
 * by the existing DesktopOnboardingOverlay, NOT by the install overlay.
 */

interface DesktopInstallOverlayProps {
  /** When false, the overlay never renders -- useful for dev when we want
   * to suppress it entirely. */
  enabled?: boolean
}

interface StageRowProps {
  descriptor: DesktopBootstrapStageDescriptor
  result: DesktopBootstrapStageResult | undefined
  now: number
}

function formatStageName(name: string): string {
  // 'system-packages' -> 'System packages'; 'uv' stays 'uv'
  if (name.length <= 3) {
    return name
  }

  return name
    .split('-')
    .map((word, i) => (i === 0 ? capitalize(word) : word))
    .join(' ')
}

function formatDuration(ms: number | null | undefined): string {
  if (typeof ms !== 'number' || !Number.isFinite(ms)) {
    return ''
  }

  if (ms < 1000) {
    return `${ms} ms`
  }

  const s = ms / 1000

  if (s < 60) {
    return `${s.toFixed(1)}s`
  }

  const m = Math.floor(s / 60)
  const rs = Math.round(s - m * 60)

  return `${m}m ${rs}s`
}

// Live elapsed for a running stage, as m:ss (or s for sub-minute).
function formatElapsed(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))

  if (s < 60) {
    return `${s}s`
  }

  const m = Math.floor(s / 60)

  return `${m}:${String(s - m * 60).padStart(2, '0')}`
}

function StageRow({ descriptor, result, now }: StageRowProps) {
  const { t } = useI18n()
  const copy = t.install
  const state: DesktopBootstrapStageState = result?.state || 'pending'

  const elapsed =
    state === 'running' && typeof result?.startedAt === 'number' ? formatElapsed(now - result.startedAt) : ''

  const icon = useMemo(() => {
    switch (state) {
      case 'running':
        return <Loader className="size-6" type="fourier-flow" />

      case 'succeeded':

      case 'skipped':
        return <Codicon className="text-muted-foreground" name="check" size="0.8125rem" />

      case 'failed':
        return <ErrorIcon size="1rem" />

      case 'pending':

      default:
        return <div className="size-1.5 rounded-full border border-(--ui-stroke-secondary)" />
    }
  }, [state])

  const reason = result?.json?.reason || result?.error || null

  return (
    <li
      className={cn(
        'flex items-center gap-3 px-4 py-2.5 transition-colors',
        state === 'running' ? 'bg-cyan-500/10 text-cyan-300' : 'hover:bg-muted/5'
      )}
    >
      <div className="flex size-5 shrink-0 items-center justify-center">
        {icon}
      </div>
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span
            className={cn(
              'truncate text-xs font-mono',
              state === 'running' ? 'font-bold text-cyan-300' : 'text-foreground/85'
            )}
          >
            {formatStageName(descriptor.name)}
          </span>
          {state === 'running' && (
            <span className="rounded bg-cyan-500/20 px-1.5 py-0.2 font-mono text-[0.625rem] font-semibold text-cyan-400 uppercase">
              ACTIVE
            </span>
          )}
        </div>
        {reason && state !== 'pending' && (
          <p className="mt-0.5 truncate font-mono text-[0.6875rem] text-muted-foreground/80">{reason}</p>
        )}
      </div>
      <span className="flex-shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
        {state === 'running' ? (elapsed ? `${copy.stageStates[state]} · ${elapsed}` : copy.stageStates[state]) : null}
        {state === 'succeeded' || state === 'skipped' ? (
          <span className="font-medium text-emerald-400/90">{formatDuration(result?.durationMs) || 'OK'}</span>
        ) : null}
        {state === 'failed' ? <span className="font-medium text-destructive">{copy.stageStates[state]}</span> : null}
      </span>
    </li>
  )
}

function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err || 'Unknown error')
}

/** Split "lead sentence\nDetails: raw" into [lead, raw]; no marker → [text, null]. */
export function splitFailureDetails(text: string | null): [string, string | null] {
  const value = (text ?? '').trim()
  const marker = value.search(/\n?\s*Details:\s*/)

  if (marker < 0) {
    return [value, null]
  }

  const lead = value.slice(0, marker).trim()
  const detail = value.slice(marker).replace(/^\s*Details:\s*/, '').trim()

  return [lead || value, detail || null]
}

import { $desktopBootstrap, applyBootstrapEvent as applyEvent, EMPTY_BOOTSTRAP_STATE as EMPTY_STATE } from '@/store/bootstrap'

export function DesktopInstallOverlay({ enabled = true }: DesktopInstallOverlayProps) {
  const { t } = useI18n()
  const copy = t.install

  const [state, setState] = useState<DesktopBootstrapState>(EMPTY_STATE)
  const [logOpen, setLogOpen] = useState(false)
  const [copied, setCopied] = useState(false)
  const [cancelling, setCancelling] = useState(false)
  const [remoteOpen, setRemoteOpen] = useState(false)
  const [now, setNow] = useState(() => Date.now())
  const logEndRef = useRef<HTMLDivElement | null>(null)

  // Tick once a second while a bootstrap is in flight so running steps show a
  // live elapsed timer. Stops when nothing is active to avoid idle renders.
  useEffect(() => {
    if (!state.active) {
      return
    }

    const id = window.setInterval(() => setNow(Date.now()), 1000)

    return () => window.clearInterval(id)
  }, [state.active])

  // Subscribe to bootstrap events + load initial snapshot
  useEffect(() => {
    if (!enabled) {
      return
    }

    const desktop = window.moorDesktop

    if (!desktop || typeof desktop.onBootstrapEvent !== 'function') {
      return
    }

    let cancelled = false

    desktop
      .getBootstrapState()
      .then(snapshot => {
        if (!cancelled && snapshot) {
          setState(snapshot)
          $desktopBootstrap.set(snapshot)
        }
      })
      .catch(() => {
        // Older Electron build without the IPC handler -- bootstrap UI just
        // stays empty, app falls through to existing onboarding flow.
      })

    const off = desktop.onBootstrapEvent(ev => {
      setState(prev => {
        const next = applyEvent(prev, ev)
        $desktopBootstrap.set(next)
        return next
      })
    })

    return () => {
      cancelled = true
      off?.()
    }
  }, [enabled])

  // Autoscroll log to bottom when new lines arrive AND the log is open
  useEffect(() => {
    if (logOpen && logEndRef.current) {
      logEndRef.current.scrollIntoView({ behavior: 'auto', block: 'end' })
    }
  }, [state.log.length, logOpen])

  // Auto-expand the log panel when a bootstrap fails so the user immediately
  // sees the install.ps1 output. Without this, the failure block shows just
  // the top-level error message and the user has to click "Show installer
  // output" to see WHY the stage failed.
  useEffect(() => {
    if (state.error) {
      setLogOpen(true)
    }
  }, [state.error])

  // The choice remains mounted while main hands off to local bootstrap. Once
  // a manifest/failure takes ownership (or a later repair presents a fresh
  // choice), this transient button state must not leak across phases — so it
  // records the root it was produced under and is read back only under that
  // same root. Deriving it beats clearing it in an effect: the choice paints
  // as soon as the first snapshot commits, and a click landing before such an
  // effect flushed would have its error wiped before it ever rendered.
  const [localStart, setLocalStart] = useState<{
    root: string | null
    starting: boolean
    error: string | null
  }>({ root: null, starting: false, error: null })

  const activeRoot = state.setupChoice?.activeRoot ?? null
  const forActiveRoot = localStart.root === activeRoot
  const localStarting = forActiveRoot && localStart.starting
  const localStartError = forActiveRoot ? localStart.error : null

  // Mount logic: show whenever a bootstrap is in flight, completed-with-error,
  // or actively running with a manifest. Hide entirely after a successful
  // completion so the rest of the UI can take over.
  const shouldShow = useMemo(() => {
    if (!enabled) {
      return false
    }

    if (state.active) {
      return true
    }

    if (state.error) {
      return true
    }

    if (state.unsupportedPlatform) {
      return true
    }

    if (state.setupChoice) {
      return true
    }

    return false
  }, [enabled, state.active, state.error, state.setupChoice, state.unsupportedPlatform])

  if (!shouldShow) {
    return null
  }

  if (remoteOpen) {
    return <FirstRunRemoteForm onBack={() => setRemoteOpen(false)} />
  }

  if (state.setupChoice) {
    return (
      <div className="fixed inset-0 z-(--z-setup) flex items-center justify-center bg-[#05070c]/90 p-4 backdrop-blur-2xl">
        <div className="w-full max-w-2xl rounded-2xl border border-cyan-500/30 bg-linear-to-b from-[#0e131f] via-[#090d16] to-[#06080e] p-8 shadow-[0_0_50px_rgba(6,182,212,0.18)] text-foreground">
          {/* Top Telemetry Header */}
          <div className="mb-6 flex items-center justify-between border-b border-cyan-500/20 pb-3 font-mono text-[0.6875rem] text-muted-foreground">
            <div className="flex items-center gap-2">
              <span className="size-1.5 rounded-full bg-cyan-400 animate-ping" />
              <span className="font-bold tracking-wider text-cyan-400 uppercase">SYSTEM INITIALIZER // RUNTIME SETUP</span>
            </div>
            <span className="text-muted-foreground/70">ENVIRONMENT: DESKTOP</span>
          </div>

          <div className="flex items-start gap-4">
            <BrandMark className="size-12 shrink-0 border-cyan-500/40" />
            <div className="min-w-0">
              <h2 className="text-xl font-bold tracking-tight text-foreground">{copy.setupChoiceTitle}</h2>
              <p className="mt-1 text-sm text-muted-foreground">{copy.setupChoiceDesc}</p>
            </div>
          </div>

          <div className="mt-6 grid gap-3.5 sm:grid-cols-2">
            <button
              className="rounded-xl border border-cyan-500/30 bg-[#0c101c]/70 p-5 text-left transition-all hover:border-cyan-400/70 hover:bg-cyan-500/10 hover:shadow-[0_0_24px_rgba(6,182,212,0.18)] group cursor-pointer"
              onClick={() => setRemoteOpen(true)}
              type="button"
            >
              <div className="flex items-center gap-2.5 text-sm font-semibold text-foreground group-hover:text-cyan-400 transition-colors">
                <div className="flex size-7 items-center justify-center rounded-lg border border-cyan-500/30 bg-cyan-500/10 text-cyan-400">
                  <Globe className="size-4" />
                </div>
                <span>{copy.connectExistingTitle}</span>
              </div>
              <p className="mt-2.5 text-xs leading-5 text-muted-foreground">{copy.connectExistingDesc}</p>
            </button>

            <button
              className="rounded-xl border border-primary/40 bg-[#0c101c]/70 p-5 text-left transition-all hover:border-primary/80 hover:bg-primary/10 hover:shadow-[0_0_24px_rgba(37,99,235,0.18)] group cursor-pointer disabled:cursor-wait disabled:opacity-60"
              disabled={localStarting}
              onClick={async () => {
                setLocalStart({ root: activeRoot, starting: true, error: null })

                try {
                  const desktop = window.moorDesktop

                  if (!desktop || typeof desktop.continueBootstrapLocal !== 'function') {
                    throw new Error(copy.localStartUnavailable)
                  }

                  await desktop.continueBootstrapLocal()
                } catch (err) {
                  setLocalStart({ root: activeRoot, starting: false, error: errorMessage(err) })
                }
              }}
              type="button"
            >
              <div className="flex items-center gap-2.5 text-sm font-semibold text-foreground group-hover:text-primary transition-colors">
                <div className="flex size-7 items-center justify-center rounded-lg border border-primary/30 bg-primary/10 text-primary">
                  {localStarting ? (
                    <Loader2 className="size-4 animate-spin text-primary" />
                  ) : (
                    <Monitor className="size-4" />
                  )}
                </div>
                <span>{copy.installLocalTitle}</span>
              </div>
              <p className="mt-2.5 text-xs leading-5 text-muted-foreground">{copy.installLocalDesc}</p>
            </button>
          </div>

          {localStartError ? (
            <div className="mt-4 flex items-start gap-2 text-sm text-destructive">
              <AlertCircle className="mt-0.5 size-4 shrink-0" />
              <span>{localStartError}</span>
            </div>
          ) : null}

          <div className="mt-6 flex items-center justify-between border-t border-cyan-500/15 pt-3 text-xs text-muted-foreground font-mono">
            <span>{copy.installTo}</span>
            <code className="text-cyan-400/90">{state.setupChoice.activeRoot}</code>
          </div>
        </div>
      </div>
    )
  }

  // Unsupported-platform branch: macOS/Linux packaged builds hit this when
  // there's no Moor Agent installed yet and we can't drive install.sh
  // (no stage protocol equivalent yet). Show a copy-paste install command
  // and the docs URL; user runs it from Terminal and relaunches the app.
  if (state.unsupportedPlatform) {
    const ups = state.unsupportedPlatform
    const platformLabel = ups.platform === 'darwin' ? 'macOS' : ups.platform === 'linux' ? 'Linux' : ups.platform

    return (
      <div className="fixed inset-0 z-(--z-setup) flex items-center justify-center bg-background/90 backdrop-blur-md">
        <div className="w-full max-w-xl rounded-xl border border-(--stroke-moor) bg-card p-8 shadow-moor">
          <h2 className="text-xl font-semibold tracking-tight">{copy.oneTimeTitle}</h2>
          <p className="mt-2 text-sm text-muted-foreground">{copy.unsupportedDesc(platformLabel)}</p>

          <div className="mt-4">
            <div className="mb-1.5 text-xs font-medium text-muted-foreground">{copy.installCommand}</div>
            <pre className="overflow-x-auto rounded-md border border-(--stroke-moor) px-3 py-2.5 font-mono text-[12px]">
              <code>{ups.installCommand}</code>
            </pre>
            <div className="mt-2 flex items-center gap-2">
              <Button
                onClick={() => {
                  void navigator.clipboard?.writeText(ups.installCommand).catch(() => {})
                }}
                size="sm"
                variant="secondary"
              >
                {copy.copyCommand}
              </Button>
              <Button
                onClick={() => {
                  window.moorDesktop?.openExternal?.(ups.docsUrl)
                }}
                size="sm"
                variant="ghost"
              >
                {copy.viewDocs}
              </Button>
            </div>
          </div>

          <div className="mt-6 flex items-center justify-between pt-2">
            <span className="text-xs text-muted-foreground">
              {copy.installTo} <code className="font-mono text-(--ui-text-secondary)">{ups.activeRoot}</code>
            </span>
            <div className="flex items-center gap-2">
              <Button onClick={() => setRemoteOpen(true)} size="sm" variant="secondary">
                <Globe className="size-4" />
                {copy.connectExistingShort}
              </Button>
              <Button onClick={() => window.location.reload()} size="sm" variant="default">
                {copy.retryAfterRun}
              </Button>
            </div>
          </div>
        </div>
      </div>
    )
  }

  const stages = state.manifest?.stages || []
  const currentStage = stages.find(s => state.stages[s.name]?.state === 'running')?.name

  const completedCount = stages.filter(
    s => state.stages[s.name]?.state === 'succeeded' || state.stages[s.name]?.state === 'skipped'
  ).length

  const totalCount = stages.length
  const failed = Boolean(state.error)
  // Main writes a plain lead sentence and keeps the raw installer error after
  // "Details:" (electron/bootstrap-failure-copy.ts); show them as two lines.
  const [failureLead, failureDetail] = splitFailureDetails(state.error)
  // Count the running stage as half-done so the bar advances *during* a long
  // stage instead of sitting frozen at the last completed step while its logs
  // stream (e.g. "0 of 2" pinned at 0% for the whole first stage).
  const progressUnits = completedCount + (!failed && currentStage ? 0.5 : 0)
  const progressPct = totalCount > 0 ? Math.round((progressUnits / totalCount) * 100) : 0
  const currentStartedAt = currentStage ? state.stages[currentStage]?.startedAt : null
  const currentElapsed = typeof currentStartedAt === 'number' ? formatElapsed(now - currentStartedAt) : ''

  return (
    <div className="fixed inset-0 z-(--z-setup) flex items-center justify-center bg-[#05070c]/90 backdrop-blur-2xl p-4 sm:p-6 select-none">
      <div className="flex w-full max-w-3xl max-h-[92vh] flex-col rounded-2xl border border-cyan-500/30 bg-linear-to-b from-[#0e131f] via-[#090d16] to-[#06080e] shadow-[0_0_50px_rgba(6,182,212,0.18)] overflow-hidden text-foreground">
        {/* Cockpit Top Status Rail */}
        <div className="flex items-center justify-between border-b border-cyan-500/20 bg-muted/10 px-6 py-2.5 font-mono text-[0.6875rem] text-muted-foreground">
          <div className="flex items-center gap-2">
            <span
              className={cn(
                'size-2 rounded-full',
                failed ? 'bg-destructive animate-pulse' : 'bg-cyan-400 animate-ping'
              )}
            />
            <span className="font-bold tracking-wider text-cyan-400 uppercase">
              {failed ? 'BOOTSTRAP ENGINE // FAILED' : 'BOOTSTRAP ENGINE // EXECUTING'}
            </span>
          </div>
          <div className="flex items-center gap-3">
            <span>PIPELINE: v{state.manifest?.protocolVersion || '2'}</span>
            <span className="text-cyan-500/30">•</span>
            <span className="tabular-nums">STAGES: {completedCount}/{totalCount}</span>
          </div>
        </div>

        {/* Header -- always visible */}
        <div className="flex flex-shrink-0 items-start gap-4 px-8 pt-6 pb-4">
          {!failed && <BrandMark className="size-12 shrink-0 border-cyan-500/40" />}
          <div className="min-w-0">
            <h2 className="text-xl font-bold tracking-tight text-foreground">
              {failed ? copy.failedTitle : state.active ? copy.settingUpTitle : copy.finishingTitle}
            </h2>
            <p className="mt-1 text-sm text-muted-foreground">{failed ? copy.failedDesc : copy.activeDesc}</p>
          </div>
        </div>

        {/* Scrollable middle: progress, stages, error block, log */}
        <div className="min-h-0 flex-1 overflow-y-auto px-8 pb-3">
          {totalCount > 0 && (
            <div className="mb-5 rounded-xl border border-cyan-500/20 bg-[#090d16]/80 p-4">
              <div className="mb-2 flex items-center justify-between text-xs font-mono text-muted-foreground">
                <span className="flex items-center gap-2">
                  <span className="text-cyan-400 font-bold">{progressPct}%</span>
                  <span>{copy.progress(completedCount, totalCount)}</span>
                  {currentStage && (
                    <span className="text-cyan-300 font-semibold">• {formatStageName(currentStage)}</span>
                  )}
                  {currentElapsed && <span className="text-muted-foreground/70">({currentElapsed})</span>}
                </span>
                <span className="tabular-nums">{completedCount} / {totalCount} COMPLETE</span>
              </div>
              <div
                aria-label="Bootstrap installation progress"
                aria-valuemax={100}
                aria-valuemin={0}
                aria-valuenow={progressPct}
                className="relative h-2 w-full overflow-hidden rounded-full bg-muted/30"
                role="progressbar"
              >
                <div
                  className={cn(
                    'h-full transition-all duration-300 ease-out',
                    failed
                      ? 'bg-destructive shadow-[0_0_12px_rgba(239,68,68,0.5)]'
                      : 'bg-linear-to-r from-cyan-500 via-blue-500 to-emerald-400 shadow-[0_0_14px_rgba(6,182,212,0.6)]'
                  )}
                  style={{ width: `${Math.max(3, progressPct)}%` }}
                />
              </div>
            </div>
          )}

          {totalCount === 0 && state.active && (
            <div className="mb-4 flex items-center gap-2.5 rounded-lg border border-cyan-500/20 bg-muted/10 p-3 text-sm text-cyan-400 font-mono">
              <Loader className="size-5 text-cyan-400" type="fourier-flow" />
              <span>{copy.fetchingManifest}</span>
            </div>
          )}

          {failed && state.error && (
            <div className="mb-4 flex items-start gap-3 rounded-xl border border-destructive/40 bg-destructive/10 p-4 text-sm">
              <ErrorIcon className="mt-0.5 shrink-0" size="1.1rem" />
              <div className="min-w-0">
                <div className="font-semibold text-destructive">{copy.error}</div>
                <p className="mt-0.5 whitespace-pre-wrap break-words text-foreground/90">{failureLead}</p>
                {failureDetail ? (
                  <p className="mt-1.5 whitespace-pre-wrap break-words font-mono text-xs text-muted-foreground">
                    {failureDetail}
                  </p>
                ) : null}
              </div>
            </div>
          )}

          {stages.length > 0 && (
            <ol className="mb-4 divide-y divide-cyan-500/10 rounded-xl border border-cyan-500/20 bg-[#080c15]/60 overflow-hidden">
              {stages.map(stage => (
                <StageRow descriptor={stage} key={stage.name} now={now} result={state.stages[stage.name]} />
              ))}
            </ol>
          )}

          <div className="pt-2">
            <Button
              className="-ml-2 text-cyan-400/80 hover:text-cyan-300 font-mono text-xs"
              onClick={() => setLogOpen(v => !v)}
              size="xs"
              type="button"
              variant="ghost"
            >
              {logOpen ? <ChevronDown className={iconSize.sm} /> : <ChevronRight className={iconSize.sm} />}
              <span>{logOpen ? copy.hideOutput : copy.showOutput}</span>
              <span className="ml-1 tabular-nums text-muted-foreground">({copy.lines(state.log.length)})</span>
            </Button>

            {logOpen && (
              <div className="mt-2.5 rounded-xl border border-cyan-500/30 bg-[#04060a] p-3 shadow-inner">
                <div className="mb-2 flex items-center justify-between border-b border-cyan-500/20 pb-1.5 font-mono text-[0.6875rem] text-muted-foreground">
                  <span className="font-semibold text-cyan-400">TELEMETRY STREAM // STDOUT &amp; STDERR</span>
                  <span className="tabular-nums">{state.log.length} events logged</span>
                </div>
                <div
                  aria-label="Installer output log"
                  aria-live="polite"
                  className={cn('overflow-y-auto font-mono text-[11px] leading-relaxed', failed ? 'max-h-80' : 'max-h-60')}
                  role="log"
                >
                  {state.log.length === 0 ? (
                    <div className="text-muted-foreground/60">{copy.noOutput}</div>
                  ) : (
                    <>
                      {state.log.map((entry, i) => (
                        <div
                          className={cn(
                            'py-0.5 whitespace-pre-wrap break-all',
                            entry.stream === 'stderr' ? 'text-amber-400/80' : 'text-foreground/85'
                          )}
                          key={i}
                        >
                          {entry.stage ? <span className="text-cyan-500/70 font-semibold">[{entry.stage}] </span> : null}
                          <span>{entry.line}</span>
                        </div>
                      ))}
                      <div ref={logEndRef} />
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Active footer */}
        {state.active && !failed && (
          <div className="flex-shrink-0 border-t border-cyan-500/20 bg-muted/5 px-8 py-3.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-xs text-muted-foreground/70">
                STAGES MONITORED VIA IPC BUS
              </span>
              <Button
                disabled={cancelling}
                onClick={async () => {
                  setCancelling(true)

                  try {
                    await window.moorDesktop?.cancelBootstrap?.()
                  } catch {
                    // ignore -- the failed/cancelled event will surface the result
                  }
                }}
                size="sm"
                variant="ghost"
              >
                {cancelling ? <Loader className="size-4" type="fourier-flow" /> : null}
                {cancelling ? copy.cancelling : copy.cancelInstall}
              </Button>
            </div>
          </div>
        )}

        {/* Footer -- always visible, never scrolls; only renders on failure */}
        {failed && (
          <div className="flex-shrink-0 bg-card p-4">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">
                {copy.transcriptSaved}{' '}
                <code className="font-mono text-(--ui-text-secondary)">%LOCALAPPDATA%\moor\logs\</code>
              </span>
              <div className="flex gap-2">
                <Button
                  onClick={() => void window.moorDesktop?.revealLogs?.().catch(() => undefined)}
                  size="sm"
                  variant="ghost"
                >
                  {copy.openLogs}
                </Button>
                <Button
                  onClick={async () => {
                    const text = state.log
                      .map(entry => (entry.stage ? `[${entry.stage}] ${entry.line}` : entry.line))
                      .join('\n')

                    const fullText = state.error ? `Error: ${state.error}\n\n${text}` : text

                    try {
                      await navigator.clipboard.writeText(fullText)
                      setCopied(true)
                      window.setTimeout(() => setCopied(false), 1500)
                    } catch {
                      // ignore -- some environments forbid clipboard writes
                    }
                  }}
                  size="sm"
                  variant="secondary"
                >
                  {copied ? copy.copiedOutput : copy.copyOutput}
                </Button>
                <Button
                  onClick={async () => {
                    // Tell main.ts to clear its latched failure BEFORE we
                    // reload. Otherwise the renderer reload calls getConnection
                    // and main short-circuits to the latched error without
                    // re-running install.ps1.
                    try {
                      await window.moorDesktop?.resetBootstrap?.()
                    } catch {
                      // best-effort -- continue with reload regardless
                    }

                    window.location.reload()
                  }}
                  size="sm"
                  variant="default"
                >
                  {copy.reloadRetry}
                </Button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
