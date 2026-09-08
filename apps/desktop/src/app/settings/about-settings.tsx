import { useStore } from '@nanostores/react'
import { useEffect, useState } from 'react'

import { BrandMark } from '@/components/brand-mark'
import { Button } from '@/components/ui/button'
import { Codicon } from '@/components/ui/codicon'
import { type Translations, useI18n } from '@/i18n'
import { AlertTriangle, Check, CheckCircle2, ExternalLink, KeyRound, Loader2, RefreshCw } from '@/lib/icons'
import { cn } from '@/lib/utils'
import {
  $desktopVersion,
  $moorTokenConfig,
  $moorTokenVerifying,
  $moorTokenVerifyResult,
  $updateApply,
  $updateChecking,
  $updateStatus,
  checkUpdates,
  loadMoorTokenConfig,
  openUpdatesWindow,
  refreshDesktopVersion,
  saveMoorTokenConfig,
  startActiveUpdate,
  verifyMoorToken
} from '@/store/updates'

import { ListRow, SectionHeading, SettingsContent } from './primitives'
import { UninstallSection } from './uninstall-section'

const RELEASE_NOTES_URL = 'https://github.com/moor-inc/moor/releases'
const INSTALLER_URL = 'https://moor-inc.github.io/moor/'

function relativeTime(ms: number | undefined, a: Translations['settings']['about']) {
  if (!ms) {
    return a.never
  }

  const diff = Date.now() - ms

  if (diff < 60_000) {
    return a.justNow
  }

  if (diff < 3_600_000) {
    return a.minAgo(Math.round(diff / 60_000))
  }

  if (diff < 86_400_000) {
    return a.hoursAgo(Math.round(diff / 3_600_000))
  }

  return a.daysAgo(Math.round(diff / 86_400_000))
}

export function AboutSettings() {
  const { t } = useI18n()
  const a = t.settings.about
  const version = useStore($desktopVersion)
  const status = useStore($updateStatus)
  const apply = useStore($updateApply)
  const checking = useStore($updateChecking)
  const [justChecked, setJustChecked] = useState(false)

  // The version atom is loaded once at app boot, which makes About show a
  // stale number after a self-update (the running binary is current, the
  // displayed string is not). Re-read on mount so opening About always
  // reflects the running build.
  useEffect(() => {
    void refreshDesktopVersion()
  }, [])

  const behind = status?.behind ?? 0
  // behind is null when the exact count is unknowable (shallow clone): the
  // backend flags that case via updateAvailable instead of a number.
  const updateAvailable = behind > 0 || Boolean(status?.updateAvailable)
  const supported = status?.supported !== false
  const applying = apply.applying || apply.stage === 'restart'

  const handleCheck = async () => {
    setJustChecked(false)
    const next = await checkUpdates()
    setJustChecked(Boolean(next))
  }

  let statusLine: string
  let statusTone: 'idle' | 'available' | 'error' = 'idle'

  if (!supported) {
    statusLine = status?.message ?? a.cantUpdate
    statusTone = 'error'
  } else if (status?.error) {
    statusLine = a.cantReach
    statusTone = 'error'
  } else if (applying) {
    statusLine = a.installing
    statusTone = 'available'
  } else if (updateAvailable) {
    statusLine = behind > 0 ? a.updateReady(behind) : a.updateReadyUnknown
    statusTone = 'available'
  } else if (status) {
    statusLine = a.onLatest
  } else {
    statusLine = a.tapCheck
  }

  return (
    <SettingsContent>
      <div className="flex flex-col items-center gap-3 pt-6 pb-2 text-center">
        <BrandMark className="size-16" />
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{a.heading}</h2>
          <p className="mt-1 text-xs text-muted-foreground">
            {version?.appVersion ? a.version(version.appVersion) : a.versionUnavailable}
          </p>
        </div>
        {(version?.bundleOutOfSync || version?.bundleSwapPending) && (
          <div className="mx-auto w-full max-w-2xl rounded-xl border border-amber-500/40 bg-amber-500/10 px-4 py-3 text-left text-sm">
            <div className="flex items-start gap-2">
              <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600 dark:text-amber-400" />
              <div className="min-w-0">
                {version?.bundleSwapPending ? (
                  // The updated app is already on disk — the updater swapped it
                  // under this running process — so a restart loads it. Saying
                  // "App build out of date" here would repeat the contradiction
                  // this banner is meant to resolve: the Updates card below
                  // already reports the runtime as current.
                  <>
                    <p className="font-medium">{a.bundleSwapPending}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{a.bundleSwapPendingDesc}</p>
                    <Button
                      className="mt-2"
                      onClick={() => void window.moorDesktop?.relaunchApp?.()}
                      size="sm"
                      variant="textStrong"
                    >
                      <RefreshCw className="size-3" />
                      {a.bundleSwapPendingAction}
                    </Button>
                  </>
                ) : (
                  <>
                    <p className="font-medium">{a.bundleOutOfSync}</p>
                    <p className="mt-1 text-xs text-muted-foreground">{a.bundleOutOfSyncDesc}</p>
                    <Button asChild className="mt-2" size="sm" variant="textStrong">
                      <a
                        href={INSTALLER_URL}
                        onClick={event => {
                          event.preventDefault()
                          void window.moorDesktop?.openExternal?.(INSTALLER_URL)
                        }}
                        rel="noreferrer"
                        target="_blank"
                      >
                        <ExternalLink className="size-3" />
                        {a.bundleOutOfSyncAction}
                      </a>
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      <div className="mx-auto mt-4 w-full max-w-2xl">
        <SectionHeading icon={RefreshCw} title={a.updates} />

        <div
          className={cn(
            'rounded-xl border px-4 py-3 text-sm',
            statusTone === 'available' && 'border-primary/30 bg-primary/5 text-foreground',
            statusTone === 'error' && 'border-destructive/35 bg-destructive/5 text-destructive',
            statusTone === 'idle' && 'border-border/70 bg-muted/20 text-foreground'
          )}
        >
          <div className="flex items-start gap-2">
            {statusTone === 'available' ? (
              <Codicon className="mt-0.5 size-4 shrink-0 text-primary" name="cloud-download" size="1rem" />
            ) : statusTone === 'error' ? null : (
              <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
            )}
            <div className="min-w-0">
              <p className="font-medium">{statusLine}</p>
              <p className="mt-1 text-xs text-muted-foreground">
                {a.lastChecked(relativeTime(status?.fetchedAt, a))}
                {justChecked && !checking ? a.justNowSuffix : ''}
              </p>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-4">
            <Button
              disabled={checking || applying || !supported}
              onClick={() => void handleCheck()}
              size="sm"
              variant="textStrong"
            >
              {checking ? <Loader2 className="size-3 animate-spin" /> : <RefreshCw className="size-3" />}
              {checking ? a.checking : a.checkNow}
            </Button>

            {updateAvailable && supported && !applying && (
              <>
                <Button onClick={() => startActiveUpdate()} size="sm">
                  {a.updateNow}
                </Button>
                <Button onClick={() => openUpdatesWindow('client')} size="sm" variant="textStrong">
                  {a.seeWhatsNew}
                </Button>
              </>
            )}

            <Button asChild className="ml-auto" size="sm" variant="text">
              <a
                href={RELEASE_NOTES_URL}
                onClick={event => {
                  event.preventDefault()
                  void window.moorDesktop?.openExternal?.(RELEASE_NOTES_URL)
                }}
                rel="noreferrer"
                target="_blank"
              >
                <ExternalLink className="size-3" />
                {a.releaseNotes}
              </a>
            </Button>
          </div>
        </div>

        <ListRow
          description={a.automaticUpdatesDesc}
          hint={a.branchCommit(status?.branch ?? 'unknown', status?.currentSha?.slice(0, 7) ?? 'unknown')}
          title={a.automaticUpdates}
        />

        <div className="mt-6">
          <SectionHeading icon={KeyRound} title="Private Repository Access" />
          <MoorPatConfigCard onTokenSaved={() => void handleCheck()} />
        </div>

        <UninstallSection />
      </div>
    </SettingsContent>
  )
}

function MoorPatConfigCard({ onTokenSaved }: { onTokenSaved?: () => void }) {
  const tokenConfig = useStore($moorTokenConfig)
  const verifying = useStore($moorTokenVerifying)
  const verifyResult = useStore($moorTokenVerifyResult)

  const [patInput, setPatInput] = useState('')
  const [repoInput, setRepoInput] = useState(tokenConfig.repo || 'moor-inc/moor')
  const [isEditing, setIsEditing] = useState(false)
  const [feedback, setFeedback] = useState<string | null>(null)

  useEffect(() => {
    void loadMoorTokenConfig()
  }, [])

  const handleSave = async () => {
    setFeedback(null)
    const patToSave = patInput.trim() || undefined
    const repoToSave = repoInput.trim() || undefined
    await saveMoorTokenConfig({ pat: patToSave, repo: repoToSave })
    if (patToSave) {
      const res = await verifyMoorToken(patToSave)
      if (res.ok) {
        setFeedback('Token verified and saved!')
        setIsEditing(false)
        setPatInput('')
        onTokenSaved?.()
      } else {
        setFeedback(res.message || 'Token verification failed.')
      }
    } else {
      setFeedback('Settings updated.')
      setIsEditing(false)
      onTokenSaved?.()
    }
  }

  const handleRemove = async () => {
    await saveMoorTokenConfig({ pat: '' })
    setPatInput('')
    setIsEditing(false)
    setFeedback('Token removed.')
    onTokenSaved?.()
  }

  return (
    <div className="mt-4 rounded-xl border border-border/70 bg-muted/20 px-4 py-3 text-sm">
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-start gap-2">
          <KeyRound className="mt-0.5 size-4 shrink-0 text-primary" />
          <div>
            <p className="font-medium">Private Repository & PAT Authentication</p>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {tokenConfig.hasPat
                ? `Token configured (${tokenConfig.maskedPat}) for updates from ${tokenConfig.repo || 'moor-inc/moor'}`
                : 'No PAT configured. Private repository checks require a token with repo read scope.'}
            </p>
          </div>
        </div>
        <Button
          onClick={() => {
            setIsEditing(!isEditing)
            setFeedback(null)
          }}
          size="xs"
          variant="outline"
        >
          {isEditing ? 'Cancel' : tokenConfig.hasPat ? 'Change' : 'Configure'}
        </Button>
      </div>

      {isEditing && (
        <div className="mt-3 space-y-2 border-t border-border/50 pt-3">
          <div>
            <label className="mb-1 block text-xs font-medium text-foreground">GitHub Personal Access Token (PAT)</label>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              onChange={e => setPatInput(e.target.value)}
              placeholder={tokenConfig.hasPat ? 'Leave blank to keep existing token' : 'ghp_... or github_pat_...'}
              type="password"
              value={patInput}
            />
          </div>

          <div>
            <label className="mb-1 block text-xs font-medium text-foreground">Target Repository</label>
            <input
              className="w-full rounded-md border border-input bg-background px-3 py-1.5 font-mono text-xs text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
              onChange={e => setRepoInput(e.target.value)}
              placeholder="moor-inc/moor"
              value={repoInput}
            />
          </div>

          <div className="flex items-center justify-between pt-1">
            {tokenConfig.hasPat ? (
              <Button className="text-destructive hover:text-destructive" onClick={handleRemove} size="xs" variant="ghost">
                Remove Token
              </Button>
            ) : <span />}
            <Button disabled={verifying} onClick={handleSave} size="xs">
              {verifying ? <Loader2 className="mr-1 size-3 animate-spin" /> : <Check className="mr-1 size-3" />}
              {verifying ? 'Verifying…' : 'Save & Verify'}
            </Button>
          </div>
        </div>
      )}

      {feedback && (
        <p className="mt-2 text-xs text-primary">{feedback}</p>
      )}
      {verifyResult && !feedback && (
        <p className={cn("mt-2 text-xs", verifyResult.ok ? "text-emerald-500" : "text-destructive")}>
          {verifyResult.message}
        </p>
      )}
    </div>
  )
}
