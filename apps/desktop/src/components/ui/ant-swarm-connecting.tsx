import { useEffect, useRef, useState } from 'react'

import { MoorAntIcon } from '@/components/brand-mark'
import { prefersReducedMotion } from '@/hooks/use-media-query'
import { cn } from '@/lib/utils'

export type SwarmSymmetryVariant = 'hexagonal' | 'gyroscopic' | 'mandala'

interface SymmetricAntParticle {
  radius: number
  initialRadius: number
  currentRadius: number
  angle: number
  initialAngle: number
  groupIndex: number
  size: number
  opacity: number
  active: boolean
  convergeProgress: number
  x: number
  y: number
  trail: Array<{ x: number; y: number }>
}

interface AbsorptionSpark {
  x: number
  y: number
  vx: number
  vy: number
  life: number
  size: number
}

interface AntSwarmConnectingProps {
  active?: boolean
  converging?: boolean
  variant?: SwarmSymmetryVariant
  className?: string
}

const CORE_RADIUS = 36

export function AntSwarmConnecting({
  active = true,
  converging = false,
  variant = 'gyroscopic',
  className
}: AntSwarmConnectingProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const beaconRef = useRef<HTMLDivElement | null>(null)
  const [telemetryStep, setTelemetryStep] = useState(0)
  const [coreFlash, setCoreFlash] = useState(false)
  const reduceMotion = prefersReducedMotion()

  // Cycle technical telemetry status
  useEffect(() => {
    if (!active) return
    const interval = window.setInterval(() => {
      setTelemetryStep(prev => (prev + 1) % 4)
    }, 900)
    return () => window.clearInterval(interval)
  }, [active])

  useEffect(() => {
    const canvas = canvasRef.current
    if (!canvas || reduceMotion) return

    const ctx = canvas.getContext('2d')
    if (!ctx) return

    let animationFrameId = 0
    let width = 0
    let height = 0
    let centerX = 0
    let centerY = 0

    const updateCenter = () => {
      const beacon = beaconRef.current
      if (beacon) {
        const beaconRect = beacon.getBoundingClientRect()
        const canvasRect = canvas.getBoundingClientRect()
        centerX = beaconRect.left + beaconRect.width / 2 - canvasRect.left
        centerY = beaconRect.top + beaconRect.height / 2 - canvasRect.top
      } else {
        centerX = width / 2
        centerY = height / 2
      }
    }

    const resize = () => {
      const parent = canvas.parentElement
      if (!parent) return
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = parent.clientWidth
      height = parent.clientHeight
      canvas.width = width * dpr
      canvas.height = height * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      updateCenter()
    }

    resize()
    window.addEventListener('resize', resize)

    // Generate mathematically symmetric particle constellation
    const particles: SymmetricAntParticle[] = []
    const sparks: AbsorptionSpark[] = []

    if (variant === 'gyroscopic') {
      // NUMBER 2: Concentric counter-rotating gyroscopic rings
      // 4 rings: 8, 12, 16, 20 nodes with uniform angular spacing (total 56 nodes)
      const ringConfigs = [
        { radius: 80, count: 8 },
        { radius: 125, count: 12 },
        { radius: 170, count: 16 },
        { radius: 215, count: 20 }
      ]
      ringConfigs.forEach((cfg, ringIdx) => {
        for (let i = 0; i < cfg.count; i++) {
          const angle = (i * 2 * Math.PI) / cfg.count
          particles.push({
            radius: cfg.radius,
            initialRadius: cfg.radius,
            currentRadius: cfg.radius,
            angle,
            initialAngle: angle,
            groupIndex: ringIdx,
            size: 2.8,
            opacity: 0.85,
            active: true,
            convergeProgress: 0,
            x: centerX + Math.cos(angle) * cfg.radius,
            y: centerY + Math.sin(angle) * cfg.radius,
            trail: []
          })
        }
      })
    } else if (variant === 'hexagonal') {
      // 6-fold radial symmetry along 6 hexagonal sectors
      const RINGS = [85, 115, 145, 175, 205, 235]
      RINGS.forEach((radius, groupIdx) => {
        const angularOffset = (groupIdx * Math.PI) / 6
        for (let sector = 0; sector < 6; sector++) {
          const angle = (sector * Math.PI) / 3 + angularOffset
          particles.push({
            radius,
            initialRadius: radius,
            currentRadius: radius,
            angle,
            initialAngle: angle,
            groupIndex: groupIdx,
            size: 2.8,
            opacity: 0.85,
            active: true,
            convergeProgress: 0,
            x: centerX + Math.cos(angle) * radius,
            y: centerY + Math.sin(angle) * radius,
            trail: []
          })
        }
      })
    } else {
      // 8-fold quantum mandala symmetry
      const RINGS = [75, 110, 145, 180, 215, 250]
      RINGS.forEach((radius, layerIdx) => {
        const phase = (layerIdx % 2) * (Math.PI / 8)
        for (let i = 0; i < 8; i++) {
          const angle = (i * 2 * Math.PI) / 8 + phase
          particles.push({
            radius,
            initialRadius: radius,
            currentRadius: radius,
            angle,
            initialAngle: angle,
            groupIndex: layerIdx,
            size: 2.8,
            opacity: 0.85,
            active: true,
            convergeProgress: 0,
            x: centerX + Math.cos(angle) * radius,
            y: centerY + Math.sin(angle) * radius,
            trail: []
          })
        }
      })
    }

    let frame = 0

    const render = (currentTime: number) => {
      frame++
      updateCenter() // Keep locked exactly to Moor emblem center

      ctx.clearRect(0, 0, width, height)

      // Draw symmetric guide rings centered exactly on the Moor emblem
      ctx.save()
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.06)'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 8])
      const guideRings =
        variant === 'gyroscopic'
          ? [80, 125, 170, 215]
          : variant === 'hexagonal'
            ? [85, 115, 145, 175, 205, 235]
            : [75, 110, 145, 180, 215, 250]

      guideRings.forEach(r => {
        ctx.beginPath()
        ctx.arc(centerX, centerY, r, 0, Math.PI * 2)
        ctx.stroke()
      })
      ctx.restore()

      // Update & render symmetric particles
      particles.forEach(p => {
        if (!p.active) return

        if (!converging) {
          if (variant === 'gyroscopic') {
            // Concentric counter-rotating rings
            const ringDir = p.groupIndex % 2 === 0 ? 1 : -1
            const ringSpeed = (0.006 + (4 - p.groupIndex) * 0.0025) * ringDir
            p.angle += ringSpeed
            p.currentRadius = p.radius
          } else if (variant === 'hexagonal') {
            const rotSpeed = 0.007 * (p.groupIndex % 2 === 0 ? 1 : -0.8)
            p.angle += rotSpeed
            const breathing = Math.sin(currentTime * 0.002 + p.groupIndex) * 5
            p.currentRadius = p.radius + breathing
          } else {
            const pulse = Math.cos(currentTime * 0.003) * 6
            p.currentRadius = p.radius + pulse
            p.angle += 0.005
          }
        } else {
          // Logarithmic spiral vortex suction inward into Moor core center
          p.convergeProgress += 0.02
          const decay = Math.min(1, p.convergeProgress)
          const easeDecay = Math.pow(decay, 1.8)
          p.currentRadius = p.initialRadius * (1 - easeDecay * 0.95)

          const vortexDir = p.groupIndex % 2 === 0 ? 1 : -1
          p.angle += (0.03 + easeDecay * 0.08) * vortexDir

          // Absorb into the core boundary
          if (p.currentRadius <= CORE_RADIUS) {
            p.active = false
            p.opacity = 0
            setCoreFlash(true)

            // Outward photonic absorption spark
            for (let i = 0; i < 3; i++) {
              sparks.push({
                x: centerX + Math.cos(p.angle) * (CORE_RADIUS - 4),
                y: centerY + Math.sin(p.angle) * (CORE_RADIUS - 4),
                vx: Math.cos(p.angle + (i - 1) * 0.5) * (1.2 + Math.random() * 1.5),
                vy: Math.sin(p.angle + (i - 1) * 0.5) * (1.2 + Math.random() * 1.5),
                life: 1.0,
                size: 1.5
              })
            }
          }
        }

        p.x = centerX + Math.cos(p.angle) * p.currentRadius
        p.y = centerY + Math.sin(p.angle) * p.currentRadius

        // Trail recording
        if (frame % 2 === 0) {
          p.trail.unshift({ x: p.x, y: p.y })
          if (p.trail.length > 6) p.trail.pop()
        }

        // Draw ant trail
        if (p.trail.length > 1) {
          ctx.beginPath()
          ctx.moveTo(p.trail[0].x, p.trail[0].y)
          for (let i = 1; i < p.trail.length; i++) {
            ctx.lineTo(p.trail[i].x, p.trail[i].y)
          }
          ctx.strokeStyle = `rgba(56, 189, 248, ${Math.max(0, p.opacity * 0.28)})`
          ctx.lineWidth = 1
          ctx.stroke()
        }

        // Render micro-ant node
        ctx.save()
        ctx.translate(p.x, p.y)
        const heading = converging ? p.angle + Math.PI / 2 + 0.4 : p.angle + Math.PI / 2
        ctx.rotate(heading)

        // Glow
        ctx.shadowColor = '#38bdf8'
        ctx.shadowBlur = 6

        // Abdomen (rear)
        ctx.fillStyle = `rgba(37, 99, 235, ${p.opacity})`
        ctx.beginPath()
        ctx.ellipse(-p.size * 1.1, 0, p.size * 0.9, p.size * 0.6, 0, 0, Math.PI * 2)
        ctx.fill()

        // Thorax (center)
        ctx.fillStyle = `rgba(56, 189, 248, ${p.opacity})`
        ctx.beginPath()
        ctx.ellipse(0, 0, p.size * 0.6, p.size * 0.45, 0, 0, Math.PI * 2)
        ctx.fill()

        // Head (front)
        ctx.fillStyle = `rgba(125, 211, 252, ${Math.min(1, p.opacity + 0.2)})`
        ctx.beginPath()
        ctx.ellipse(p.size * 0.9, 0, p.size * 0.5, p.size * 0.4, 0, 0, Math.PI * 2)
        ctx.fill()

        // Antennae
        ctx.strokeStyle = `rgba(56, 189, 248, ${p.opacity * 0.9})`
        ctx.lineWidth = 0.8
        ctx.beginPath()
        ctx.moveTo(p.size * 1.1, -p.size * 0.15)
        ctx.lineTo(p.size * 1.8, -p.size * 0.7)
        ctx.moveTo(p.size * 1.1, p.size * 0.15)
        ctx.lineTo(p.size * 1.8, p.size * 0.7)
        ctx.stroke()

        ctx.restore()
      })

      // Draw dynamic web lines
      ctx.save()
      if (variant === 'gyroscopic') {
        ctx.strokeStyle = 'rgba(37, 99, 235, 0.18)'
        for (let i = 0; i < particles.length; i++) {
          for (let j = i + 1; j < particles.length; j++) {
            if (
              particles[i].active &&
              particles[j].active &&
              Math.abs(particles[i].groupIndex - particles[j].groupIndex) === 1
            ) {
              const dx = particles[i].x - particles[j].x
              const dy = particles[i].y - particles[j].y
              if (dx * dx + dy * dy < 3800) {
                ctx.beginPath()
                ctx.moveTo(particles[i].x, particles[i].y)
                ctx.lineTo(particles[j].x, particles[j].y)
                ctx.stroke()
              }
            }
          }
        }
      } else {
        ctx.strokeStyle = 'rgba(56, 189, 248, 0.14)'
        for (let i = 0; i < particles.length; i++) {
          for (let j = i + 1; j < particles.length; j++) {
            if (particles[i].active && particles[j].active && particles[i].groupIndex === particles[j].groupIndex) {
              const dx = particles[i].x - particles[j].x
              const dy = particles[i].y - particles[j].y
              if (dx * dx + dy * dy < 18000) {
                ctx.beginPath()
                ctx.moveTo(particles[i].x, particles[i].y)
                ctx.lineTo(particles[j].x, particles[j].y)
                ctx.stroke()
              }
            }
          }
        }
      }
      ctx.restore()

      // Render sparks
      for (let i = sparks.length - 1; i >= 0; i--) {
        const s = sparks[i]
        s.x += s.vx
        s.y += s.vy
        s.life -= 0.04
        if (s.life <= 0) {
          sparks.splice(i, 1)
          continue
        }
        ctx.fillStyle = `rgba(125, 211, 252, ${s.life})`
        ctx.fillRect(s.x, s.y, s.size, s.size)
      }

      animationFrameId = requestAnimationFrame(render)
    }

    animationFrameId = requestAnimationFrame(render)

    return () => {
      cancelAnimationFrame(animationFrameId)
      window.removeEventListener('resize', resize)
    }
  }, [converging, reduceMotion, variant])

  const telemetryLabels = [
    'COLONY MESH // DISCOVERING WORKER NODES',
    'PHEROMONE PROTOCOL // ESTABLISHING CARRIER',
    'AUTONOMOUS AGENT // ROUTING SYNAPSE',
    'GATEWAY LINK // SECURING LOCALHOST INTERFACE'
  ]

  const symmetryLabel =
    variant === 'gyroscopic' ? 'CONCENTRIC GYRO' : variant === 'hexagonal' ? '6-FOLD RADIAL' : '8-FOLD MANDALA'

  return (
    <div
      className={cn(
        'relative flex size-full items-center justify-center select-none overflow-hidden',
        className
      )}
    >
      {/* Background Particle Canvas */}
      <canvas
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 size-full"
        ref={canvasRef}
      />

      {/* Dead-Centered Central Hexagonal Core Beacon */}
      <div
        className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-10 flex size-24 items-center justify-center pointer-events-none"
        ref={beaconRef}
      >
        {/* Rotating decorative geometric antenna ring */}
        <div
          className={cn(
            'absolute inset-0 rounded-full border border-cyan-500/25 border-t-cyan-400',
            !reduceMotion && 'animate-spin'
          )}
          style={{ animationDuration: '6s' }}
        />
        <div
          className={cn(
            'absolute -inset-2.5 rounded-full border border-dashed border-primary/20 border-b-cyan-500/40',
            !reduceMotion && 'animate-spin'
          )}
          style={{ animationDuration: '12s', animationDirection: 'reverse' }}
        />

        {/* Central Moor Brand Emblem with absorption shockwave flash */}
        <div
          className={cn(
            'relative flex size-18 items-center justify-center rounded-2xl border border-cyan-500/40 bg-[#090b10]/90 p-3.5 shadow-[0_0_35px_rgba(56,189,248,0.25)] backdrop-blur-md transition-all duration-300',
            coreFlash && 'shadow-[0_0_55px_rgba(56,189,248,0.65)] border-cyan-300 scale-105'
          )}
        >
          <MoorAntIcon className="size-full animate-pulse" />
        </div>
      </div>

      {/* Telemetry & Connection Status - Anchored Below the Centered Core */}
      <div
        aria-live="polite"
        className="absolute top-[calc(50%+4.25rem)] left-1/2 -translate-x-1/2 z-10 flex flex-col items-center gap-2 text-center pointer-events-none w-full max-w-sm"
      >
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-cyan-400 shadow-[0_0_8px_#38bdf8] animate-ping" />
          <h1 className="font-mono text-xs font-bold tracking-[0.25em] text-cyan-400 uppercase">
            {converging ? 'COLONY LINK ESTABLISHED' : 'SWARM CONSTELLATION LINK'}
          </h1>
        </div>

        <p className="font-mono text-[0.6875rem] text-muted-foreground/80 tracking-wide transition-all duration-300">
          {converging ? 'MOUNTING WORKSTATION ENVIRONMENT' : telemetryLabels[telemetryStep]}
        </p>

        {/* Real-time system matrix readout */}
        <div className="mt-2 flex items-center gap-3 rounded-md border border-cyan-500/20 bg-muted/10 px-3 py-1 font-mono text-[0.625rem] text-muted-foreground">
          <span>NODES: 56 ACTIVE</span>
          <span className="text-cyan-500/40">•</span>
          <span>SYMMETRY: {symmetryLabel}</span>
          <span className="text-cyan-500/40">•</span>
          <span>BUS: PHEROMONE-IPC</span>
          <span className="text-cyan-500/40">•</span>
          <span>LATENCY: &lt;1ms</span>
        </div>
      </div>
    </div>
  )
}
