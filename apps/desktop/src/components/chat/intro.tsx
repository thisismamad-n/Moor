import { useState } from 'react'

import { BrandMark } from '@/components/brand-mark'
import { Cpu, Layers3, Terminal, Zap } from '@/lib/icons'
import { capitalize, normalize } from '@/lib/text'
import { cn } from '@/lib/utils'

import introCopyJsonl from './intro-copy.jsonl?raw'
import { Wordmark } from './wordmark'

type IntroCopy = {
  headline: string
  body: string
}

type IntroCopyRecord = IntroCopy & {
  personality: string
}

export type IntroProps = {
  personality?: string
  seed?: number
}

const NEUTRAL_PERSONALITIES = new Set(['', 'default', 'none', 'neutral'])

const FALLBACK_COPY: IntroCopy[] = [
  {
    headline: 'What are we moving today?',
    body: "Send a bug, branch, plan, or rough idea. I'll inspect the repo and turn it into the next concrete step."
  },
  {
    headline: "What's on your mind?",
    body: "Bring the code, question, or stuck part. I'll read the room before making changes."
  },
  {
    headline: 'What should Moor look at?',
    body: "Send the task, failing path, or half-formed plan. I'll help turn it into action."
  },
  {
    headline: 'Where should we start?',
    body: "Bring the problem, goal, or file. I'll inspect first and keep the next step concrete."
  },
  {
    headline: 'What needs attention?',
    body: "Send the context you have. I'll help sort it into a plan or a fix."
  }
]

function normalizeKey(value?: string): string {
  return normalize(value)
}

function titleize(value: string): string {
  return value
    .split(/[-_\s]+/)
    .filter(Boolean)
    .map(capitalize)
    .join(' ')
}

function isIntroCopyRecord(value: unknown): value is IntroCopyRecord {
  if (!value || typeof value !== 'object') {
    return false
  }

  const record = value as Record<string, unknown>

  return (
    typeof record.personality === 'string' &&
    typeof record.headline === 'string' &&
    typeof record.body === 'string' &&
    Boolean(record.personality.trim()) &&
    Boolean(record.headline.trim()) &&
    Boolean(record.body.trim())
  )
}

function parseIntroCopy(raw: string): Record<string, IntroCopy[]> {
  const byPersonality: Record<string, IntroCopy[]> = {}

  for (const line of raw.split(/\r?\n/)) {
    const trimmed = line.trim()

    if (!trimmed) {
      continue
    }

    try {
      const parsed: unknown = JSON.parse(trimmed)

      if (!isIntroCopyRecord(parsed)) {
        continue
      }

      const key = normalizeKey(parsed.personality)
      byPersonality[key] ??= []
      byPersonality[key].push({
        headline: parsed.headline.trim(),
        body: parsed.body.trim()
      })
    } catch {
      // Bad generated copy should not break the whole desktop app.
    }
  }

  return byPersonality
}

const INTRO_COPY_BY_PERSONALITY = parseIntroCopy(introCopyJsonl)

function neutralCopy(): IntroCopy[] {
  return INTRO_COPY_BY_PERSONALITY.none || INTRO_COPY_BY_PERSONALITY.default || FALLBACK_COPY
}

function fallbackCopyForPersonality(personalityKey: string): IntroCopy[] {
  if (NEUTRAL_PERSONALITIES.has(personalityKey)) {
    return neutralCopy()
  }

  const label = titleize(personalityKey)

  return [
    {
      headline: `${label} mode is on. What should we work on?`,
      body: "Send the task, file, or rough idea. I'll use your configured voice and keep the work grounded in this repo."
    },
    {
      headline: `What does ${label} Moor need to see?`,
      body: "Bring the context or the stuck part. I'll adapt to your configured personality."
    },
    {
      headline: `${label} mode is ready.`,
      body: "Send the problem, file, or idea. I'll follow the personality you've configured."
    },
    {
      headline: `What should ${label} Moor tackle?`,
      body: "Drop the task here. I'll keep the work grounded in the repo."
    },
    {
      headline: 'Where should we begin?',
      body: `Give me the context and I'll answer in ${label} mode.`
    }
  ]
}

function pickCopy(copies: IntroCopy[], seed = 0): IntroCopy {
  return copies[Math.abs(seed) % copies.length] || FALLBACK_COPY[0]
}

const WORDMARK = 'MOOR AGENT'

function resolveCopy(personality?: string, seed?: number): IntroCopy {
  const personalityKey = normalizeKey(personality)

  const copies = NEUTRAL_PERSONALITIES.has(personalityKey)
    ? INTRO_COPY_BY_PERSONALITY[personalityKey] || neutralCopy()
    : INTRO_COPY_BY_PERSONALITY[personalityKey] || fallbackCopyForPersonality(personalityKey)

  return pickCopy(copies, seed)
}

interface PresetCard {
  id: string
  title: string
  command: string
  prompt: string
  description: string
  icon: typeof Cpu
}

const PRESET_CARDS: PresetCard[] = [
  {
    id: 'inspect',
    title: 'Inspect Architecture',
    command: '/inspect',
    prompt: '/inspect map codebase architecture, entry points and boundaries',
    description: 'Map module boundaries, entry points & active invariants',
    icon: Cpu
  },
  {
    id: 'audit',
    title: 'Security & Quality Audit',
    command: '/audit',
    prompt: '/audit verify recent changes for security and contract integrity',
    description: 'Audit changes for security, regressions & standard contracts',
    icon: Layers3
  },
  {
    id: 'tests',
    title: 'Execute Test Suite',
    command: 'run tests',
    prompt: 'scripts/run_tests.sh',
    description: 'Run tests with subprocess isolation & verify contract integrity',
    icon: Terminal
  },
  {
    id: 'goal',
    title: 'Autonomous Objective',
    command: '/goal',
    prompt: '/goal ',
    description: 'Run deep autonomous loop until goal is fully verified',
    icon: Zap
  }
]

function applyPresetPrompt(promptText: string) {
  const input = document.querySelector<HTMLElement>('[data-slot="composer-rich-input"]')
  if (!input) return
  input.focus()
  input.textContent = promptText
  input.dispatchEvent(new Event('input', { bubbles: true }))
  const range = document.createRange()
  const selection = window.getSelection()
  range.selectNodeContents(input)
  range.collapse(false)
  selection?.removeAllRanges()
  selection?.addRange(range)
}

export function Intro({ personality, seed }: IntroProps) {
  const [mountSeed] = useState(() => Math.floor(Math.random() * 100000))
  const copy = resolveCopy(personality, mountSeed + (seed ?? 0))

  return (
    <div
      className="flex w-full min-w-0 flex-col items-center justify-center px-4 py-8 text-center text-muted-foreground sm:px-6 lg:px-8"
      data-slot="aui_intro"
    >
      <div className="flex flex-col items-center w-full max-w-xl min-w-0 pointer-events-none">
        <BrandMark className="mb-4 size-16" />
        <Wordmark className="mb-2" text={WORDMARK} />
        <p className="m-0 text-center leading-normal tracking-tight text-sm text-muted-foreground max-w-md">
          {copy.body}
        </p>

        {/* 1-Click Quick-Start Preset Cards */}
        <div className="mt-8 grid w-full grid-cols-1 gap-2.5 sm:grid-cols-2 pointer-events-auto text-left">
          {PRESET_CARDS.map(preset => {
            const Icon = preset.icon
            return (
              <button
                key={preset.id}
                className={cn(
                  'group flex flex-col justify-between rounded-xl border p-3.5 transition-all duration-200 text-left cursor-pointer',
                  'border-border/70 bg-card/60 hover:border-primary/50 hover:bg-card/90 hover:shadow-xs active:scale-[0.99]',
                  'dark:border-cyan-500/20 dark:bg-[#11141c]/70 dark:hover:border-cyan-500/40 dark:hover:shadow-[0_0_20px_rgba(37,99,235,0.15)]'
                )}
                onClick={() => applyPresetPrompt(preset.prompt)}
                type="button"
              >
                <div className="flex items-center justify-between w-full mb-1.5">
                  <span className="flex items-center gap-1.5 font-semibold text-xs text-foreground group-hover:text-primary transition-colors">
                    <Icon className="size-3.5 text-primary/80" />
                    {preset.title}
                  </span>
                  <span className="font-mono text-[0.625rem] rounded border border-border/60 bg-muted/40 px-1.5 py-0.5 text-muted-foreground group-hover:border-primary/40 group-hover:text-primary">
                    {preset.command}
                  </span>
                </div>
                <p className="text-[0.6875rem] text-muted-foreground leading-snug line-clamp-2">
                  {preset.description}
                </p>
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
