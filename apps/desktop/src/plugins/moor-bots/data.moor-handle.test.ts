/**
 * @moor belongs to the default bot only while its source has no real
 * (pre-reservation) `moor` profile. With one, the roster shows exactly one
 * @moor — the real profile — and the default answers to @default, so a
 * typed @moor reaches the same profile the backend's message_agent does.
 */

import { describe, expect, it, vi } from 'vitest'

import { botHandle, botMentionTag, claimDefaultHandles, mergeMultiSourceRoster, resolveRosterMentions } from './data'
import { previewKind } from './row-helpers'
import type { RosterRow } from './types'

vi.mock('@moor/plugin-sdk', async () => {
  const { atom } = await import('nanostores')

  return { atom, host: {}, queryClient: undefined, useQuery: vi.fn(), useValue: vi.fn() }
})

vi.mock('./shared', () => ({ getPluginCtx: () => null, ID: 'moor-bots' }))

function roster(names: string[]): RosterRow[] {
  const local = { profiles: names.map(name => ({ name })) }

  // What Electron's buildAgentRoster reports for a single local source: bare-name handles.
  const union = {
    agents: names.map(profile => ({
      connectionId: 'local',
      connectionKind: 'local' as const,
      connectionLabel: 'This device',
      handle: profile,
      profile,
      targetProfile: profile
    })),
    primaryConnectionId: 'local'
  }

  return mergeMultiSourceRoster(local, union, 'local').profiles as RosterRow[]
}

describe('the @moor handle', () => {
  it.each([
    [['default', 'researcher'], 'default'],
    [['default', 'moor', 'researcher'], 'moor']
  ])('roster %j shows one @moor and a typed @moor reaches %s', (names, owner) => {
    const rows = roster(names)
    const handles = rows.map(row => botHandle(row.name, row))

    expect(handles.filter(handle => handle === 'moor')).toHaveLength(1)
    expect(rows.map(row => botMentionTag(row)).filter(tag => tag === 'moor')).toHaveLength(1)
    expect(resolveRosterMentions('@moor ping', rows, { name: 'researcher' }).map(row => row.name)).toEqual([owner])
  })

  it('names the default @default once a real moor profile holds the handle', () => {
    const rows = roster(['default', 'moor', 'researcher'])
    const byName = Object.fromEntries(rows.map(row => [row.name, botHandle(row.name, row)]))

    expect(byName).toEqual({ default: 'default', moor: 'moor', researcher: 'researcher' })
    expect(resolveRosterMentions('@default ping', rows, { name: 'researcher' }).map(row => row.name)).toEqual(['default'])
  })

  it('keeps each source separate: a remote moor profile does not rename the local default', () => {
    const rows = claimDefaultHandles<Partial<RosterRow>>([
      { connectionId: 'local', name: 'default' },
      { connectionId: 'mini', name: 'default' },
      { connectionId: 'mini', name: 'moor' }
    ])

    expect(rows.map(row => botHandle(String(row.name), row))).toEqual(['moor', 'default', 'moor'])
  })

  it("never lets a source's stale 'moor' handle on its default answer @moor", () => {
    // An older backend labels its default @moor even beside a real moor profile.
    const rows = claimDefaultHandles<RosterRow>([
      { connectionId: 'mini', handle: 'moor', name: 'default', remoteSource: true },
      { connectionId: 'mini', handle: 'moor', name: 'moor', remoteSource: true },
      { connectionId: 'local', name: 'researcher' }
    ])

    expect(resolveRosterMentions('@moor ping', rows, { name: 'researcher' }).map(row => row.name)).toEqual(['moor'])
  })

  it('names a DM sender in a row preview by its roster handle', () => {
    const rows = claimDefaultHandles<RosterRow>(
      ['default', 'moor', 'researcher'].map(name => ({ connectionId: 'local', name }))
    )

    const sender = (name: string, list: RosterRow[]) =>
      previewKind(`Message from 🤖 ${name} (@x): hi`, list, 'local').fromBot

    expect([sender('default', rows), sender('moor', rows)]).toEqual(['default', 'moor'])
    // No real moor profile: the default is still @moor (#89484).
    expect(sender('default', claimDefaultHandles<RosterRow>([{ connectionId: 'local', name: 'default' }]))).toBe(
      'moor'
    )
  })
})
