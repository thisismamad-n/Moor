import { useStore } from '@nanostores/react'
import { atom } from 'nanostores'
import { useEffect } from 'react'

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
  preventCloseButtonAutoFocus
} from '@/components/ui/dialog'
import { Command, Cpu, Layers3, MessageSquareText, Send, Terminal } from '@/lib/icons'
import { cn } from '@/lib/utils'

export const $keyboardShortcutsOpen = atom<boolean>(false)
export const openKeyboardShortcuts = () => $keyboardShortcutsOpen.set(true)
export const closeKeyboardShortcuts = () => $keyboardShortcutsOpen.set(false)
export const toggleKeyboardShortcuts = () => $keyboardShortcutsOpen.set(!$keyboardShortcutsOpen.get())

interface ShortcutEntry {
  combo: string
  description: string
  category: 'Navigation' | 'Execution' | 'Workspace'
}

const SHORTCUTS: ShortcutEntry[] = [
  { category: 'Navigation', combo: '1', description: 'Switch to Chat workstation' },
  { category: 'Navigation', combo: '2', description: 'Switch to Skills & Tools catalog' },
  { category: 'Navigation', combo: '3', description: 'Switch to Artifacts inspector' },
  { category: 'Navigation', combo: '4', description: 'Switch to Messaging gateway' },
  { category: 'Navigation', combo: '5', description: 'Toggle Terminal pane' },
  { category: 'Navigation', combo: 'Ctrl+K / Cmd+K', description: 'Open Command Center' },
  { category: 'Navigation', combo: 'Ctrl+P / Cmd+P', description: 'Quick Command Palette' },
  { category: 'Execution', combo: 'Ctrl+Enter', description: 'Send message / execute turn' },
  { category: 'Execution', combo: 'Esc', description: 'Cancel current generation / close modal' },
  { category: 'Execution', combo: 'Ctrl+N / Cmd+N', description: 'Start fresh session' },
  { category: 'Execution', combo: 'Ctrl+Shift+A', description: 'Focus agent composer' },
  { category: 'Workspace', combo: 'Ctrl+B / Cmd+B', description: 'Toggle Left Sidebar' },
  { category: 'Workspace', combo: 'Ctrl+J / Cmd+J', description: 'Toggle Terminal takeover' },
  { category: 'Workspace', combo: 'Ctrl+F / Cmd+F', description: 'Find in session thread' },
  { category: 'Workspace', combo: '?', description: 'Open this Keyboard Shortcuts cheatsheet' }
]

export function KeyboardShortcutsModal() {
  const open = useStore($keyboardShortcutsOpen)

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't trigger '?' inside inputs or textareas
      const target = e.target as HTMLElement | null
      const isInput =
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target?.isContentEditable ||
        Boolean(target?.closest('[data-slot="composer-rich-input"]'))

      if (e.key === '?' && !isInput && !e.ctrlKey && !e.metaKey && !e.altKey) {
        e.preventDefault()
        toggleKeyboardShortcuts()
      }
    }

    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [])

  const categories = ['Navigation', 'Execution', 'Workspace'] as const

  return (
    <Dialog onOpenChange={openKeyboardShortcuts => $keyboardShortcutsOpen.set(openKeyboardShortcuts)} open={open}>
      <DialogContent
        bodyClassName="p-6 gap-5"
        className="max-w-xl border-border/80 bg-background text-foreground dark:border-cyan-500/30 dark:bg-[#0c0f16]"
        onOpenAutoFocus={preventCloseButtonAutoFocus}
      >
        <div className="flex flex-col gap-1 text-left">
          <div className="flex items-center gap-2">
            <span className="flex size-7 items-center justify-center rounded-lg border border-primary/40 bg-primary/10 text-primary font-mono text-xs font-bold">
              ?
            </span>
            <DialogTitle className="text-lg font-bold tracking-tight">Keyboard Shortcuts Cheatsheet</DialogTitle>
          </div>
          <DialogDescription className="text-xs text-muted-foreground">
            Direct navigation, execution triggers, and workstation hotkeys for high-speed operation.
          </DialogDescription>
        </div>

        <div className="grid gap-5">
          {categories.map(cat => (
            <div className="space-y-2" key={cat}>
              <h4 className="text-[0.6875rem] font-bold uppercase tracking-widest text-primary/80">{cat}</h4>
              <div className="divide-y divide-border/40 rounded-lg border border-border/60 bg-muted/20">
                {SHORTCUTS.filter(s => s.category === cat).map(s => (
                  <div className="flex items-center justify-between px-3 py-2 text-xs" key={s.combo}>
                    <span className="text-muted-foreground">{s.description}</span>
                    <kbd className="rounded border border-border/70 bg-background/80 px-2 py-0.5 font-mono text-[0.6875rem] font-semibold text-foreground shadow-xs dark:border-border/50">
                      {s.combo}
                    </kbd>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  )
}
