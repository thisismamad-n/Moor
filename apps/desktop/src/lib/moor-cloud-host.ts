/**
 * The Webapp tab is served BY a Moor Cloud agent (its own origin is the
 * agent). Cloud then owns every update: the app itself comes from that agent.
 * Kept free of the session store so low-level modules (notifications, the
 * settings manifest) can ask it without an import cycle.
 */

import { isMoorCloudUrl } from '@moor/shared'

import { isBrowserHostedDesktop } from '@/lib/platform'

export function servedByMoorCloud(): boolean {
  return typeof window !== 'undefined' && isBrowserHostedDesktop() && isMoorCloudUrl(window.location.origin)
}
