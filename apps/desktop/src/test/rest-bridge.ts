import { vi } from 'vitest'

import type { MoorApiRequest } from '@/global'

/** Install a fake `window.moorDesktop.api`, the preload bridge every REST helper sends through. */
export function installRestBridge(answer: (request: MoorApiRequest) => object) {
  const api = vi.fn(async (request: MoorApiRequest) => answer(request))

  Object.defineProperty(window, 'moorDesktop', { configurable: true, value: { api } })

  return api
}
