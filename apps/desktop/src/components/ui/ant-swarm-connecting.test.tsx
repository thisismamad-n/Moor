// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AntSwarmConnecting } from './ant-swarm-connecting'

describe('AntSwarmConnecting', () => {
  it('renders canvas and beacon icon without errors', () => {
    const { container } = render(<AntSwarmConnecting active={true} />)

    const canvas = container.querySelector('canvas')
    expect(canvas).toBeTruthy()

    // Ensure the central ant mark is present
    const antIcon = container.querySelector('svg')
    expect(antIcon).toBeTruthy()

    // Telemetry display should show initial technical status
    expect(screen.getByText(/SWARM CONSTELLATION LINK/i)).toBeTruthy()
    expect(screen.getByText(/NODES: 64 ACTIVE/i)).toBeTruthy()
    expect(screen.getByText(/BUS: PHEROMONE-IPC/i)).toBeTruthy()
  })

  it('renders reduced motion fallback gracefully', () => {
    const { container } = render(<AntSwarmConnecting active={true} />)
    expect(container.firstElementChild).toBeTruthy()
  })

  it('applies converging state text when converging=true', () => {
    render(<AntSwarmConnecting active={true} converging={true} />)
    expect(screen.getByText(/COLONY LINK ESTABLISHED/i)).toBeTruthy()
    expect(screen.getByText(/MOUNTING WORKSTATION ENVIRONMENT/i)).toBeTruthy()
  })
})

