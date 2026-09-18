// @vitest-environment jsdom
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { AntSwarmConnecting } from './ant-swarm-connecting'

describe('AntSwarmConnecting', () => {
  it('renders canvas and beacon icon without any text descriptions', () => {
    const { container } = render(<AntSwarmConnecting active={true} />)

    const canvas = container.querySelector('canvas')
    expect(canvas).toBeTruthy()

    // Ensure the central ant mark is present
    const antIcon = container.querySelector('svg')
    expect(antIcon).toBeTruthy()

    // Explicitly verify zero text descriptions in the loader animation
    expect(container.textContent?.trim()).toBe('')
  })

  it('renders gyroscopic variant with pure animation and no text', () => {
    const { container } = render(<AntSwarmConnecting active={true} variant="gyroscopic" />)
    expect(container.querySelector('canvas')).toBeTruthy()
    expect(container.textContent?.trim()).toBe('')
  })

  it('renders hexagonal variant with pure animation and no text', () => {
    const { container } = render(<AntSwarmConnecting active={true} variant="hexagonal" />)
    expect(container.querySelector('canvas')).toBeTruthy()
    expect(container.textContent?.trim()).toBe('')
  })

  it('renders mandala variant with pure animation and no text', () => {
    const { container } = render(<AntSwarmConnecting active={true} variant="mandala" />)
    expect(container.querySelector('canvas')).toBeTruthy()
    expect(container.textContent?.trim()).toBe('')
  })

  it('renders reduced motion fallback gracefully without text', () => {
    const { container } = render(<AntSwarmConnecting active={true} />)
    expect(container.firstElementChild).toBeTruthy()
    expect(container.textContent?.trim()).toBe('')
  })

  it('renders converging state purely with animation and zero text descriptions', () => {
    const { container } = render(<AntSwarmConnecting active={true} converging={true} />)
    expect(container.querySelector('canvas')).toBeTruthy()
    expect(container.querySelector('svg')).toBeTruthy()
    expect(container.textContent?.trim()).toBe('')
  })
})
