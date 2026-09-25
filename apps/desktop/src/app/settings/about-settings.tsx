import { useStore } from '@nanostores/react'
import { type ReactElement, useEffect } from 'react'

import { UpdateStatusCard, VersionHero } from '@/components/update-status'
import { VersionDetails } from '@/components/version-details'
import { useI18n } from '@/i18n'
import { RefreshCw } from '@/lib/icons'
import { $connection } from '@/store/session'
import { $desktopVersion, checkBackendUpdates, refreshDesktopVersion } from '@/store/updates'

import { SectionHeading, SettingsContent } from './primitives'
import { SETTING_IDS, settingElementId } from './settings-manifest'
import { UninstallSection } from './uninstall-section'
import { useSettingDeepLink } from './use-setting-deep-link'

interface AboutSettingsProps {
  subpage?: string
}

export function AboutSettings({ subpage }: AboutSettingsProps = {}): ReactElement {
  useSettingDeepLink('about', page => subpage === undefined || page === subpage)

  if (subpage === 'uninstall') {
    return (
      <SettingsContent>
        <UninstallSection />
      </SettingsContent>
    )
  }

  return <AppUpdatesSettings includeUninstall={subpage === undefined} />
}

interface AppUpdatesSettingsProps {
  includeUninstall: boolean
}

function AppUpdatesSettings({ includeUninstall }: AppUpdatesSettingsProps): ReactElement {
  const { t } = useI18n()
  const version = useStore($desktopVersion)
  const connection = useStore($connection)
  const remote = connection?.mode === 'remote'

  // Refresh the running version when About opens or the active gateway changes.
  useEffect((): void => {
    void refreshDesktopVersion()

    if (remote) {
      void checkBackendUpdates()
    }
  }, [connection, remote])

  return (
    <SettingsContent>
      <VersionHero version={version} />
      <div className="mx-auto mt-4 w-full max-w-2xl">
        <SectionHeading icon={RefreshCw} title={t.settings.about.updates} />
        <div className="grid gap-3" id={settingElementId(SETTING_IDS.about.updates)}>
          <UpdateStatusCard target="client" />
          {/* Client and remote backend updates are independent. Only the client has release notes. */}
          {remote && <UpdateStatusCard showReleaseNotes={false} target="backend" />}
        </div>
        {version && <VersionDetails version={version} />}
        {includeUninstall && <UninstallSection />}
      </div>
    </SettingsContent>
  )
}

function MoorPatConfigCard({ onTokenSaved }: { onTokenSaved?: () => void }) {
  const tokenConfig = useStore($moorTokenConfig)
  const verifying = useStore($moorTokenVerifying)
  const verifyResult = useStore($moorTokenVerifyResult)

  const [patInput, setPatInput] = useState('')
  const [repoInput, setRepoInput] = useState(tokenConfig.repo || 'thisismamad-n/Moor')
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
                ? `Token configured (${tokenConfig.maskedPat}) for updates from ${tokenConfig.repo || 'thisismamad-n/Moor'}`
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
              placeholder='thisismamad-n/Moor'
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
