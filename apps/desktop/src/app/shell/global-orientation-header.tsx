import { useStore } from '@nanostores/react'
import { useEffect, useState } from 'react'
import { useLocation, useNavigate } from 'react-router'

import {
  ARTIFACTS_ROUTE,
  MESSAGING_ROUTE,
  navigateToWorkspacePage,
  NEW_CHAT_ROUTE,
  SETTINGS_ROUTE,
  SKILLS_ROUTE
} from '@/app/routes'
import { $terminalTakeover, setTerminalTakeover } from '@/app/right-sidebar/store'
import { BrandMark } from '@/components/brand-mark'
import { openKeyboardShortcuts } from '@/components/keyboard-shortcuts-modal'
import { toggleLayoutEditMode } from '@/components/pane-shell/edit-mode'
import { Button } from '@/components/ui/button'
import { Tip } from '@/components/ui/tooltip'
import {
  Activity,
  ArrowLeftRight,
  Check,
  Copy,
  Cpu,
  FolderOpen,
  Layers3,
  LayoutGrid,
  Lock,
  MessageSquareText,
  PanelLeft,
  PanelRight,
  Send,
  Settings,
  Terminal,
  Zap
} from '@/lib/icons'
import { useStoreSelector } from '@/lib/use-session-slice'
import { cn } from '@/lib/utils'
import { writeClipboardText } from '@/components/ui/copy-button'
import {
  $fileBrowserOpen,
  $panesFlipped,
  $sidebarOpen,
  toggleFileBrowserOpen,
  togglePanesFlipped,
  toggleSidebarOpen
} from '@/store/layout'
import { projectNameForCwd } from '@/store/projects'
import { $connection, $sessions } from '@/store/session'
import { $focusedSessionState, $focusedStoredSessionId } from '@/store/session-states'
import { $subagentsBySession } from '@/store/subagents'

export function GlobalOrientationHeader() {
  const location = useLocation()
  const navigate = useNavigate()
  const connection = useStore($connection)
  const terminalTakeover = useStore($terminalTakeover)
  const focusedStoredId = useStore($focusedStoredSessionId)
  const sessions = useStore($sessions)
  const sidebarOpen = useStore($sidebarOpen)
  const fileBrowserOpen = useStore($fileBrowserOpen)
  const panesFlipped = useStore($panesFlipped)

  const focusedSession = sessions.find(s => s.id === focusedStoredId)
  const focusedTitle = focusedSession?.title?.trim() || ''

  const focusedCwd = useStoreSelector($focusedSessionState, s => s?.cwd?.trim() || '')
  const focusedBusy = useStoreSelector($focusedSessionState, s => Boolean(s?.busy || s?.turnLive))
  const focusedModel = useStoreSelector($focusedSessionState, s => s?.model?.trim() || '')
  const focusedBranch = useStoreSelector($focusedSessionState, s => s?.branch?.trim() || '')

  const activeSubagents = useStoreSelector($subagentsBySession, bySession =>
    Object.values(bySession).reduce((sum, items) => sum + items.length, 0)
  )

  const [copiedCwd, setCopiedCwd] = useState(false)

  const projectName = projectNameForCwd(focusedCwd) || (focusedCwd ? focusedCwd.split(/[\\/]/).filter(Boolean).pop() : 'Default Workspace')
  const pathname = location.pathname

  const isChatActive = pathname === '/' || (!pathname.startsWith('/skills') && !pathname.startsWith('/artifacts') && !pathname.startsWith('/messaging') && !pathname.startsWith('/settings') && !pathname.startsWith('/command-center'))
  const isSkillsActive = pathname.startsWith('/skills')
  const isArtifactsActive = pathname.startsWith('/artifacts')
  const isMessagingActive = pathname.startsWith('/messaging')
  const isTerminalActive = terminalTakeover

  // Global hotkeys [1]-[5]
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null
      const isInput =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target?.isContentEditable ||
        Boolean(target?.closest('[data-slot="composer-rich-input"]'))

      if (isInput || e.altKey || e.shiftKey) {
        return
      }

      // Check for standalone 1-5 or Ctrl/Cmd + 1-5
      const key = e.key
      if (['1', '2', '3', '4', '5'].includes(key)) {
        if (e.ctrlKey || e.metaKey || !isInput) {
          e.preventDefault()
          if (key === '1') {
            navigateToWorkspacePage(navigate, NEW_CHAT_ROUTE)
          } else if (key === '2') {
            navigateToWorkspacePage(navigate, SKILLS_ROUTE)
          } else if (key === '3') {
            navigateToWorkspacePage(navigate, ARTIFACTS_ROUTE)
          } else if (key === '4') {
            navigateToWorkspacePage(navigate, MESSAGING_ROUTE)
          } else if (key === '5') {
            setTerminalTakeover(!terminalTakeover)
          }
        }
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [navigate, terminalTakeover])

  const handleCopyCwd = () => {
    if (!focusedCwd) return
    void writeClipboardText(focusedCwd).then(() => {
      setCopiedCwd(true)
      setTimeout(() => setCopiedCwd(false), 1800)
    })
  }

  const modeLabel = connection?.mode === 'remote' ? 'Remote' : 'Local'

  return (
    <header
      className="relative z-20 flex h-9 shrink-0 items-center justify-between border-b border-border/80 bg-(--ui-bg-chrome) px-2 text-xs text-foreground backdrop-blur-md select-none dark:border-cyan-500/20 dark:bg-[#090b10]/95"
      data-slot="global-orientation-header"
      style={{
        paddingRight: 'calc(var(--titlebar-tools-right, 0px) + 8px)'
      }}
    >
      {/* ── Zone 1: Left Context Segment ("Never Get Lost") ───────────────── */}
      <div className="flex min-w-0 shrink-0 items-center gap-1.5">
        {/* Sidebar Toggle Button */}
        <Tip label={sidebarOpen ? 'Hide Sidebar [Ctrl+B / Cmd+B]' : 'Show Sidebar [Ctrl+B / Cmd+B]'}>
          <button
            aria-label="Toggle Sidebar"
            className={cn(
              'flex size-6.5 items-center justify-center rounded-md border transition-colors',
              sidebarOpen
                ? 'border-border/80 bg-muted/40 text-foreground hover:bg-muted/70'
                : 'border-border/50 bg-muted/20 text-muted-foreground hover:bg-muted/40 hover:text-foreground'
            )}
            onClick={toggleSidebarOpen}
            type="button"
          >
            <PanelLeft className="size-3.5" />
          </button>
        </Tip>

        {/* Moor Brand Emblem */}
        <div className="flex items-center gap-1.5 px-1">
          <BrandMark bare className="size-4.5" />
          <span className="font-mono text-[0.6875rem] font-black tracking-wider text-foreground">
            MOOR
          </span>
        </div>

        <div className="h-3.5 w-px bg-border/80 dark:bg-cyan-500/20" />

        {/* Active Session Chip */}
        <Tip label={focusedTitle ? `Active Session: ${focusedTitle}` : 'Primary Workspace Session'}>
          <div className="flex max-w-[140px] items-center gap-1.5 truncate rounded-md border border-border/70 bg-muted/30 px-2 py-0.5 text-xs font-medium text-foreground transition-colors hover:bg-muted/50 dark:border-cyan-500/20">
            <span
              className={cn(
                'size-1.5 shrink-0 rounded-full',
                focusedBusy ? 'animate-ping bg-primary' : 'bg-emerald-500 dark:bg-cyan-400'
              )}
            />
            <span className="truncate">{focusedTitle || 'Active Session'}</span>
            {focusedBranch && (
              <span className="shrink-0 font-mono text-[0.625rem] text-muted-foreground">
                {focusedBranch}
              </span>
            )}
          </div>
        </Tip>

        {/* Project CWD Chip */}
        <Tip label={focusedCwd ? `CWD: ${focusedCwd} (Click to copy)` : 'Current Working Directory'}>
          <button
            aria-label={focusedCwd ? `Copy current working directory ${focusedCwd}` : 'Copy working directory'}
            className="flex max-w-[150px] items-center gap-1.5 truncate rounded-md border border-border/60 bg-muted/20 px-2 py-0.5 text-xs font-medium text-muted-foreground transition-all hover:border-primary/40 hover:bg-muted/40 hover:text-foreground active:scale-98"
            onClick={handleCopyCwd}
            type="button"
          >
            <FolderOpen className="size-3 shrink-0 text-primary/80" />
            <span className="truncate">{projectName}</span>
            {copiedCwd ? (
              <Check className="size-2.5 shrink-0 text-emerald-500" />
            ) : (
              <Copy className="size-2.5 shrink-0 opacity-40 hover:opacity-100" />
            )}
          </button>
        </Tip>

        {/* Connection Mode Badge */}
        <Tip label={`Gateway Mode: ${modeLabel} • Active Connection`}>
          <div className="flex items-center gap-1.5 rounded-full border border-border/60 bg-muted/20 px-2 py-0.5 text-[0.6875rem] font-medium text-muted-foreground">
            <span className="size-1.5 rounded-full bg-emerald-500 dark:bg-emerald-400" />
            <span>{modeLabel}</span>
          </div>
        </Tip>

        {/* Active Model Pill */}
        {focusedModel && (
          <Tip label={`Active Model: ${focusedModel}`}>
            <div className="flex items-center gap-1 rounded-md border border-primary/30 bg-primary/10 px-2 py-0.5 font-mono text-[0.6875rem] font-semibold text-primary">
              <Zap className="size-2.5" />
              <span className="max-w-[100px] truncate">{focusedModel}</span>
            </div>
          </Tip>
        )}

        {/* Execution / Lock Status */}
        <Tip label={focusedBusy ? 'Agent loop currently executing' : 'Workstation ready for interaction'}>
          <div
            className={cn(
              'flex items-center gap-1 rounded-md px-1.5 py-0.5 font-mono text-[0.625rem] font-bold uppercase tracking-wider',
              focusedBusy
                ? 'border border-primary/40 bg-primary/20 text-primary animate-pulse'
                : 'text-muted-foreground/80'
            )}
          >
            {focusedBusy ? (
              <>
                <Activity className="size-2.5 animate-spin" />
                <span>EXEC</span>
              </>
            ) : (
              <>
                <Lock className="size-2.5 opacity-60" />
                <span>READY</span>
              </>
            )}
          </div>
        </Tip>
      </div>

      {/* ── Zone 2: Center Navigation Tabs ([1]-[5]) ──────────────────────── */}
      <nav aria-label="Workstation Navigation" className="flex flex-1 items-center justify-center gap-1 px-2 min-w-0">
        {/* Tab 1: Chat */}
        <button
          className={cn(
            'group relative flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all shrink-0',
            isChatActive
              ? 'border border-primary/40 bg-primary/15 text-primary shadow-xs dark:border-cyan-500/40 dark:text-cyan-400'
              : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground'
          )}
          onClick={() => navigateToWorkspacePage(navigate, NEW_CHAT_ROUTE)}
          type="button"
        >
          <MessageSquareText className="size-3.5" />
          <span>Chat</span>
          {activeSubagents > 0 && (
            <span className="flex size-4 items-center justify-center rounded-full bg-primary text-[0.625rem] font-bold text-primary-foreground">
              {activeSubagents}
            </span>
          )}
          <kbd className="ml-0.5 rounded border border-border/60 bg-muted/30 px-1 py-0.2 font-mono text-[0.625rem] font-normal opacity-70 group-hover:opacity-100">
            [1]
          </kbd>
        </button>

        {/* Tab 2: Skills */}
        <button
          className={cn(
            'group relative flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all shrink-0',
            isSkillsActive
              ? 'border border-primary/40 bg-primary/15 text-primary shadow-xs dark:border-cyan-500/40 dark:text-cyan-400'
              : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground'
          )}
          onClick={() => navigateToWorkspacePage(navigate, SKILLS_ROUTE)}
          type="button"
        >
          <Cpu className="size-3.5" />
          <span>Skills</span>
          <kbd className="ml-0.5 rounded border border-border/60 bg-muted/30 px-1 py-0.2 font-mono text-[0.625rem] font-normal opacity-70 group-hover:opacity-100">
            [2]
          </kbd>
        </button>

        {/* Tab 3: Artifacts */}
        <button
          className={cn(
            'group relative flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all shrink-0',
            isArtifactsActive
              ? 'border border-primary/40 bg-primary/15 text-primary shadow-xs dark:border-cyan-500/40 dark:text-cyan-400'
              : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground'
          )}
          onClick={() => navigateToWorkspacePage(navigate, ARTIFACTS_ROUTE)}
          type="button"
        >
          <Layers3 className="size-3.5" />
          <span>Artifacts</span>
          <kbd className="ml-0.5 rounded border border-border/60 bg-muted/30 px-1 py-0.2 font-mono text-[0.625rem] font-normal opacity-70 group-hover:opacity-100">
            [3]
          </kbd>
        </button>

        {/* Tab 4: Messaging */}
        <button
          className={cn(
            'group relative flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all shrink-0',
            isMessagingActive
              ? 'border border-primary/40 bg-primary/15 text-primary shadow-xs dark:border-cyan-500/40 dark:text-cyan-400'
              : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground'
          )}
          onClick={() => navigateToWorkspacePage(navigate, MESSAGING_ROUTE)}
          type="button"
        >
          <Send className="size-3.5" />
          <span>Messaging</span>
          <kbd className="ml-0.5 rounded border border-border/60 bg-muted/30 px-1 py-0.2 font-mono text-[0.625rem] font-normal opacity-70 group-hover:opacity-100">
            [4]
          </kbd>
        </button>

        {/* Tab 5: Terminal */}
        <button
          className={cn(
            'group relative flex items-center gap-1.5 rounded-md px-2.5 py-1 text-xs font-semibold transition-all shrink-0',
            isTerminalActive
              ? 'border border-primary/40 bg-primary/15 text-primary shadow-xs dark:border-cyan-500/40 dark:text-cyan-400'
              : 'text-muted-foreground hover:bg-muted/40 hover:text-foreground'
          )}
          onClick={() => setTerminalTakeover(!terminalTakeover)}
          type="button"
        >
          <Terminal className="size-3.5" />
          <span>Terminal</span>
          <kbd className="ml-0.5 rounded border border-border/60 bg-muted/30 px-1 py-0.2 font-mono text-[0.625rem] font-normal opacity-70 group-hover:opacity-100">
            [5]
          </kbd>
        </button>
      </nav>

      {/* ── Zone 3: Right Layout & System Tools ───────────────────────────── */}
      <div className="flex shrink-0 items-center gap-1 pl-1">
        {/* Flip Panes Toggle */}
        <Tip label={panesFlipped ? 'Restore Pane Order [Cmd+\\ / Ctrl+\\]' : 'Swap Pane Sides [Cmd+\\ / Ctrl+\\]'}>
          <Button
            aria-label="Swap Panes"
            className="size-6.5 rounded-md border border-border/60 p-0 text-muted-foreground hover:border-primary/40 hover:bg-muted/40 hover:text-foreground"
            onClick={togglePanesFlipped}
            size="xs"
            variant="ghost"
          >
            <ArrowLeftRight className="size-3.5" />
          </Button>
        </Tip>

        {/* Right Sidebar Toggle */}
        <Tip label={fileBrowserOpen ? 'Hide Right Panel [Ctrl+Shift+B]' : 'Show Right Panel [Ctrl+Shift+B]'}>
          <Button
            aria-label="Toggle Right Sidebar"
            className={cn(
              'size-6.5 rounded-md border p-0 transition-colors',
              fileBrowserOpen
                ? 'border-primary/40 bg-primary/10 text-primary'
                : 'border-border/60 text-muted-foreground hover:border-primary/40 hover:bg-muted/40 hover:text-foreground'
            )}
            onClick={toggleFileBrowserOpen}
            size="xs"
            variant="ghost"
          >
            <PanelRight className="size-3.5" />
          </Button>
        </Tip>

        {/* Layout Editor Mode */}
        <Tip label="Layout Editor Mode">
          <Button
            aria-label="Layout Editor"
            className="size-6.5 rounded-md border border-border/60 p-0 text-muted-foreground hover:border-primary/40 hover:bg-muted/40 hover:text-foreground"
            onClick={toggleLayoutEditMode}
            size="xs"
            variant="ghost"
          >
            <LayoutGrid className="size-3.5" />
          </Button>
        </Tip>

        {/* Cheatsheet Modal Trigger '?' */}
        <Tip label="Keyboard Shortcuts Cheatsheet [?]">
          <Button
            aria-label="Shortcuts Cheatsheet"
            className="size-6.5 rounded-md border border-border/70 p-0 font-mono text-xs font-bold text-muted-foreground hover:border-primary/40 hover:bg-muted/40 hover:text-foreground"
            onClick={openKeyboardShortcuts}
            size="xs"
            variant="ghost"
          >
            ?
          </Button>
        </Tip>

        {/* Settings Button */}
        <Tip label="Settings">
          <Button
            aria-label="Open Settings"
            className="size-6.5 rounded-md border border-border/60 p-0 text-muted-foreground hover:border-primary/40 hover:bg-muted/40 hover:text-foreground"
            onClick={() => navigate(SETTINGS_ROUTE)}
            size="xs"
            variant="ghost"
          >
            <Settings className="size-3.5" />
          </Button>
        </Tip>
      </div>
    </header>
  )
}

