import { useEffect, useRef, useState } from 'react'

import { MoorAntIcon } from '@/components/brand-mark'
import { prefersReducedMotion } from '@/hooks/use-media-query'
import { cn } from '@/lib/utils'

interface AntParticle {
  x: number
  y: number
  vx: number
  vy: number
  targetRadius: number
  targetAngle: number
  angle: number
  speed: number
  size: number
  opacity: number
  antennaAngle: number
  trail: Array<{ x: number; y: number }>
}

interface AntSwarmConnectingProps {
  active?: boolean
  converging?: boolean
  className?: string
}

export function AntSwarmConnecting({
  active = true,
  converging = false,
  className
}: AntSwarmConnectingProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null)
  const [telemetryStep, setTelemetryStep] = useState(0)
  const reduceMotion = prefersReducedMotion()

  // Cycle technical telemetry
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

    const resize = () => {
      const parent = canvas.parentElement
      if (!parent) return
      const dpr = Math.min(window.devicePixelRatio || 1, 2)
      width = parent.clientWidth
      height = parent.clientHeight
      canvas.width = width * dpr
      canvas.height = height * dpr
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0)
      centerX = width / 2
      centerY = height / 2
    }

    resize()
    window.addEventListener('resize', resize)

    // Generate ant swarm nodes
    const PARTICLE_COUNT = 48
    const particles: AntParticle[] = []

    for (let i = 0; i < PARTICLE_COUNT; i++) {
      const angle = (i / PARTICLE_COUNT) * Math.PI * 2 + (Math.random() - 0.5) * 0.4
      const dist = 90 + Math.random() * 180
      particles.push({
        x: centerX + Math.cos(angle) * dist,
        y: centerY + Math.sin(angle) * dist,
        vx: 0,
        vy: 0,
        targetRadius: 75 + (i % 5) * 28,
        targetAngle: angle,
        angle: angle + Math.PI / 2,
        speed: 0.006 + Math.random() * 0.008,
        size: 2.2 + Math.random() * 1.6,
        opacity: 0.4 + Math.random() * 0.5,
        antennaAngle: 0.5 + Math.random() * 0.3,
        trail: []
      })
    }

    let frame = 0

    const render = () => {
      frame++
      ctx.clearRect(0, 0, width, height)

      // Draw faint cybernetic colony guide tracks
      ctx.save()
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.05)'
      ctx.lineWidth = 1
      ctx.setLineDash([4, 8])
      ;[80, 115, 150, 190].forEach(radius => {
        ctx.beginPath()
        ctx.arc(centerX, centerY, radius, 0, Math.PI * 2)
        ctx.stroke()
      })
      ctx.restore()

      // Update & render particles
      particles.forEach((p, idx) => {
        if (converging) {
          // Accelerate inwards towards the central emblem
          const dx = centerX - p.x
          const dy = centerY - p.y
          p.x += dx * 0.12
          p.y += dy * 0.12
          p.opacity = Math.max(0, p.opacity - 0.04)
        } else {
          // Orbit along constellation highway
          p.targetAngle += (idx % 2 === 0 ? 1 : -1) * p.speed
          const targetX = centerX + Math.cos(p.targetAngle) * p.targetRadius
          const targetY = centerY + Math.sin(p.targetAngle) * p.targetRadius

          p.x += (targetX - p.x) * 0.06
          p.y += (targetY - p.y) * 0.06

          // Calculate heading
          const nextAngle = Math.atan2(targetY - p.y, targetX - p.x)
          p.angle = nextAngle
        }

        // Store trail
        if (frame % 3 === 0) {
          p.trail.unshift({ x: p.x, y: p.y })
          if (p.trail.length > 5) p.trail.pop()
        }

        // Draw ant pheromone trail
        if (p.trail.length > 1 && !converging) {
          ctx.beginPath()
          ctx.moveTo(p.x, p.y)
          p.trail.forEach(t => ctx.lineTo(t.x, t.y))
          ctx.strokeStyle = `rgba(56, 189, 248, ${p.opacity * 0.25})`
          ctx.lineWidth = 1
          ctx.stroke()
        }

        // Render stylized micro-ant node
        ctx.save()
        ctx.translate(p.x, p.y)
        ctx.rotate(p.angle)

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

        // Tiny antennae sensory rays
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

      // Draw dynamic web lines between nearby ants
      ctx.save()
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.12)'
      ctx.lineWidth = 0.75
      for (let i = 0; i < particles.length; i++) {
        for (let j = i + 1; j < particles.length; j++) {
          const dx = particles[i].x - particles[j].x
          const dy = particles[i].y - particles[j].y
          const distSq = dx * dx + dy * dy
          if (distSq < 2800) {
            ctx.beginPath()
            ctx.moveTo(particles[i].x, particles[i].y)
            ctx.lineTo(particles[j].x, particles[j].y)
            ctx.stroke()
          }
        }
      }
      ctx.restore()

      animationFrameId = requestAnimationFrame(render)
    }

    render()

    return () => {
      cancelAnimationFrame(animationFrameId)
      window.removeEventListener('resize', resize)
    }
  }, [converging, reduceMotion])

  const telemetryLabels = [
    'COLONY MESH // DISCOVERING WORKER NODES',
    'PHEROMONE PROTOCOL // ESTABLISHING CARRIER',
    'AUTONOMOUS AGENT // ROUTING SYNAPSE',
    'GATEWAY LINK // SECURING LOCALHOST INTERFACE'
  ]

  return (
    <div
      className={cn(
        'relative flex size-full flex-col items-center justify-center select-none overflow-hidden',
        className
      )}
    >
      {/* Background Particle Canvas */}
      <canvas
        aria-hidden="true"
        className="pointer-events-none absolute inset-0 size-full"
        ref={canvasRef}
      />

      {/* Central Hexagonal Core Beacon */}
      <div className="relative z-10 flex flex-col items-center gap-6">
        <div className="relative flex size-24 items-center justify-center">
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

          {/* Central Moor Brand Emblem */}
          <div className="relative flex size-18 items-center justify-center rounded-2xl border border-cyan-500/40 bg-[#090b10]/90 p-3.5 shadow-[0_0_35px_rgba(56,189,248,0.25)] backdrop-blur-md">
            <MoorAntIcon className="size-full animate-pulse" />
          </div>
        </div>

        {/* Telemetry & Connection Status */}
        <div aria-live="polite" className="flex flex-col items-center gap-2 text-center">
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
            <span>NODES: 64 ACTIVE</span>
            <span className="text-cyan-500/40">•</span>
            <span>BUS: PHEROMONE-IPC</span>
            <span className="text-cyan-500/40">•</span>
            <span>LATENCY: &lt;1ms</span>
          </div>
        </div>
      </div>
    </div>
  )
}
