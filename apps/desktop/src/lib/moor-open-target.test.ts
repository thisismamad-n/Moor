import { describe, expect, it } from 'vitest'

import {
  normalizeMoorOpenString,
  pathFromMoorDeepLink,
  pathFromOpenDeepLink,
  resolveMoorOpenPath
} from './moor-open-target'

describe('normalizeMoorOpenString', () => {
  it('accepts hash-router paths and strips a leading hash', () => {
    expect(normalizeMoorOpenString('/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeMoorOpenString('#/index-network/intent/1')).toBe('/index-network/intent/1')
  })

  it('maps plugin-scoped moor:// deep links to the same path', () => {
    expect(normalizeMoorOpenString('moor://index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeMoorOpenString('moor://index-network/intent/1?focus=true')).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('maps moor://open/… deep links by stripping the open host', () => {
    expect(normalizeMoorOpenString('moor://open/index-network/intent/1')).toBe('/index-network/intent/1')
    expect(normalizeMoorOpenString('moor://open/settings/plugins')).toBe('/settings/plugins')
  })

  it('rejects reserved moor kinds and unsafe paths', () => {
    expect(normalizeMoorOpenString('moor://blueprint/morning-brief')).toBeNull()
    expect(normalizeMoorOpenString('moor://plugin/install')).toBeNull()
    expect(normalizeMoorOpenString('https://example.com/x')).toBeNull()
    expect(normalizeMoorOpenString('/../etc/passwd')).toBeNull()
    expect(normalizeMoorOpenString('index-network')).toBeNull()
  })
})

describe('resolveMoorOpenPath', () => {
  it('merges structured path + params', () => {
    expect(resolveMoorOpenPath({ path: '/index-network/intent/1', params: { focus: 'true' } })).toBe(
      '/index-network/intent/1?focus=true'
    )
  })

  it('resolves href the same as a bare string', () => {
    expect(resolveMoorOpenPath({ href: 'moor://index-network/intent/1' })).toBe('/index-network/intent/1')
  })
})

describe('pathFromMoorDeepLink', () => {
  it('builds the navigate path from a plugin-scoped deep-link payload', () => {
    expect(pathFromMoorDeepLink('index-network', 'intent/1')).toBe('/index-network/intent/1')
  })

  it('builds the navigate path from moor://open/… payloads', () => {
    expect(pathFromOpenDeepLink('index-network/intent/1')).toBe('/index-network/intent/1')
    expect(pathFromMoorDeepLink('open', 'agent/42')).toBe('/agent/42')
  })

  it('ignores reserved kinds', () => {
    expect(pathFromMoorDeepLink('blueprint', 'morning-brief')).toBeNull()
    expect(pathFromMoorDeepLink('plugin', 'install')).toBeNull()
  })
})
