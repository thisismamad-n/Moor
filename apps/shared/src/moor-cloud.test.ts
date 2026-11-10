import { describe, expect, it } from 'vitest'

import { isMoorCloudUrl } from './moor-cloud'

describe('isMoorCloudUrl', () => {
  it('recognises production and staging agent hosts, nothing else', () => {
    expect(isMoorCloudUrl('https://ares-3009.agents.nousresearch.com')).toBe(true)
    expect(isMoorCloudUrl('https://ares--app.agents.staging-nousresearch.com/')).toBe(true)
    expect(isMoorCloudUrl('https://agents.nousresearch.com.evil.example')).toBe(false)
    expect(isMoorCloudUrl('https://my-box.tailnet.ts.net')).toBe(false)
    expect(isMoorCloudUrl('not a url')).toBe(false)
    expect(isMoorCloudUrl(undefined)).toBe(false)
  })
})
