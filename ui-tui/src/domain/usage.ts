import type { Usage } from '@moor/shared/gateway-events'

export { usageFromTick } from '@moor/shared/usage-tick'

export const ZERO: Usage = { calls: 0, input: 0, output: 0, total: 0 }
