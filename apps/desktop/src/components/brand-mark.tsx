import { cn } from '@/lib/utils'

export interface BrandMarkProps extends React.ComponentProps<'span'> {
  /** Render compact icon without outer container box */
  bare?: boolean
}

/**
 * Moor Core Brand Emblem
 *
 * Geometric hexagonal cybernetic emblem fusing the Moor 'M' architecture
 * with the ant archetype (structure, sensory antennae, and mandible power).
 * Rendered in scalable SVG with adaptive cyber-obsidian/cobalt and titanium styling.
 */
export function MoorAntIcon({ className }: { className?: string }) {
  return (
    <svg
      aria-label="Moor Brand Emblem"
      className={cn('size-full select-none', className)}
      fill="none"
      viewBox="0 0 64 64"
      xmlns="http://www.w3.org/2000/svg"
    >
      <defs>
        <linearGradient id="moorCobaltGrad" x1="0%" x2="100%" y1="0%" y2="100%">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="50%" stopColor="#2563eb" />
          <stop offset="100%" stopColor="#1d4ed8" />
        </linearGradient>
        <linearGradient id="moorHexGrad" x1="0%" x2="0%" y1="0%" y2="100%">
          <stop offset="0%" stopColor="#2563eb" stopOpacity="0.25" />
          <stop offset="100%" stopColor="#06b6d4" stopOpacity="0.05" />
        </linearGradient>
      </defs>

      {/* Hexagonal outer perimeter */}
      <polygon
        className="stroke-primary/40 dark:stroke-cyan-500/40"
        fill="url(#moorHexGrad)"
        points="32,4 56,18 56,46 32,60 8,46 8,18"
        strokeWidth="1.5"
      />

      {/* Inner architectural grid notches */}
      <circle className="fill-primary/60 dark:fill-cyan-400/80" cx="32" cy="4" r="1.5" />
      <circle className="fill-primary/60 dark:fill-cyan-400/80" cx="56" cy="18" r="1.5" />
      <circle className="fill-primary/60 dark:fill-cyan-400/80" cx="56" cy="46" r="1.5" />
      <circle className="fill-primary/60 dark:fill-cyan-400/80" cx="32" cy="60" r="1.5" />
      <circle className="fill-primary/60 dark:fill-cyan-400/80" cx="8" cy="46" r="1.5" />
      <circle className="fill-primary/60 dark:fill-cyan-400/80" cx="8" cy="18" r="1.5" />

      {/* Antennae - upper sensory vectors */}
      <path
        className="stroke-primary dark:stroke-cyan-400"
        d="M26 22 L20 12 L13 14"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.2"
      />
      <path
        className="stroke-primary dark:stroke-cyan-400"
        d="M38 22 L44 12 L51 14"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2.2"
      />

      {/* Head & Sensory node */}
      <polygon
        className="fill-primary/20 stroke-primary dark:fill-cyan-500/20 dark:stroke-cyan-300"
        points="32,18 39,24 32,29 25,24"
        strokeWidth="1.8"
      />
      <circle className="fill-cyan-400 dark:fill-cyan-300" cx="32" cy="23.5" r="1.8" />

      {/* Core 'M' & Thorax / Mandibles Architecture */}
      <path
        d="M17 44 L25 29 L32 37 L39 29 L47 44"
        fill="none"
        stroke="url(#moorCobaltGrad)"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="3.4"
      />

      {/* Center thorax bridge */}
      <path
        className="stroke-primary dark:stroke-cyan-400"
        d="M25 39 L32 45 L39 39"
        fill="none"
        strokeLinecap="round"
        strokeLinejoin="round"
        strokeWidth="2"
      />

      {/* Lower Abdomen / Sub-mandible anchor */}
      <polygon
        className="fill-primary/30 stroke-primary dark:fill-blue-600/30 dark:stroke-cyan-400"
        points="32,46 37,52 32,55 27,52"
        strokeWidth="1.6"
      />

      {/* Central power node */}
      <circle className="fill-cyan-400 dark:fill-white" cx="32" cy="37" r="2.2" />
    </svg>
  )
}

export function BrandMark({ className, bare = false, ...props }: BrandMarkProps) {
  if (bare) {
    return <MoorAntIcon className={className} />
  }

  return (
    <span
      className={cn(
        'relative inline-flex size-14 shrink-0 items-center justify-center overflow-hidden rounded-xl border p-2 transition-all duration-300',
        'border-border/80 bg-linear-to-br from-white to-slate-100/90 shadow-sm',
        'dark:border-cyan-500/30 dark:bg-linear-to-br dark:from-[#11141c] dark:via-[#0c0f16] dark:to-[#090b10] dark:shadow-[0_0_24px_rgba(37,99,235,0.2)]',
        className
      )}
      {...props}
    >
      <MoorAntIcon className="size-full" />
    </span>
  )
}
