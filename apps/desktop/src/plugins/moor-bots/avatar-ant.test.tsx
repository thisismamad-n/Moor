// @vitest-environment jsdom
import { render } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { ANT_CASTES, BotFace, defaultShapeFor, isAntCaste } from './avatar'
import type { AntCaste } from './types'

describe('Ant Castes procedural avatar rendering', () => {
  it('identifies valid ant castes and rejects other shapes', () => {
    for (const caste of ANT_CASTES) {
      expect(isAntCaste(caste)).toBe(true)
    }

    expect(isAntCaste('circle')).toBe(false)
    expect(isAntCaste('hexagon')).toBe(false)
    expect(isAntCaste('blobatar')).toBe(false)
    expect(isAntCaste(undefined)).toBe(false)
  })

  it('defaultShapeFor returns one of the 5 ant castes for any bot name', () => {
    const names = ['inbox-triage', 'code-reviewer', 'moor-bot', 'architect-agent', 'ops-sentry']
    for (const name of names) {
      const shape = defaultShapeFor(name)
      expect(isAntCaste(shape)).toBe(true)
      expect(ANT_CASTES).toContain(shape as AntCaste)
    }
  })

  it('renders procedural SVG for each caste with data-ant-caste and data-bot-face', () => {
    for (const caste of ANT_CASTES) {
      const { container } = render(
        <BotFace color="#06b6d4" name={`test-${caste}`} shape={caste} size={48} />
      )

      const svg = container.querySelector('svg')
      expect(svg).toBeTruthy()
      expect(svg?.getAttribute('data-bot-face')).toBe(`test-${caste}`)
      expect(svg?.getAttribute('data-ant-caste')).toBe(caste)
      expect(svg?.getAttribute('width')).toBe('48')
      expect(svg?.getAttribute('height')).toBe('48')

      // Ensure zero emojis in the output SVG
      expect(container.textContent).not.toMatch(/[\u{1F300}-\u{1F9FF}]/u)
    }
  })
})
