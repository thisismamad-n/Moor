import { skillCatalogInstallIdentifier } from '@moor/shared'
import { useQuery } from '@tanstack/react-query'

export type CatalogKind = 'skills' | 'plugins'

export interface CatalogEntry {
  id: string
  name: string
  description: string
  overview: string
  category: string
  categoryLabel: string
  source: string
  author: string
  identifier: string
  installIdentifier?: string | null
  repo: string
  sha: string
  subdir: string
  version: string
  requiresMoor: string
  tags: string[]
  platforms: string[]
  requirements: string[]
  tools: string[]
  hooks: string[]
  sourceUrl: string | null
  docsUrl: string | null
  stars: number | null
  search: string
}

const DOCS_ORIGIN = 'https://raw.githubusercontent.com/thisismamad-n/Moor/master'
// The primary catalog base points to Moor's GitHub raw assets; fallback mirrors upstream if needed.
const CATALOG_BASE = 'https://raw.githubusercontent.com/thisismamad-n/Moor/master/website/static/api'
const FALLBACK_CATALOG_BASE = 'https://nousresearch.github.io/hermes-agent/docs/api'
const text = (value: unknown): string => typeof value === 'string' ? value : ''
const strings = (value: unknown): string[] => Array.isArray(value) ? value.filter(v => typeof v === 'string') : []

function webUrl(value: unknown): string | null {
  try {
    const url = new URL(text(value))

    return url.protocol === 'https:' || url.protocol === 'http:' ? url.href : null
  } catch {
    return null
  }
}

export function parseCatalog(kind: CatalogKind, data: unknown): CatalogEntry[] {
  if (!Array.isArray(data)) {
    throw new Error('Invalid catalog response')
  }

  const entries = new Map<string, CatalogEntry>()

  for (const row of data) {
    if (!row || typeof row !== 'object' || !text(row.name)) {
      continue
    }

    const name = text(row.name)
    const source = text(kind === 'plugins' ? row.tier : row.source)
    const identifier = text(row.identifier) || name
    const id = `${source}:${identifier}`
    const caps = row.capabilities ?? {}
    const category = text(row.category) || 'uncategorized'
    const tags = strings(row.tags)
    const tools = strings(caps.providesTools)
    const hooks = strings(caps.providesHooks)
    const author = text(row.maintainer ?? row.author)
    const description = text(row.description)

    entries.set(id, {
      id,
      name,
      description,
      overview: text(row.overview),
      category,
      categoryLabel: text(row.categoryLabel) || category,
      source,
      author,
      identifier,
      installIdentifier: kind === 'skills' ? skillCatalogInstallIdentifier({
        name, source, identifier: text(row.identifier), installIdentifier: text(row.installIdentifier)
      }) : null,
      repo: text(row.repo),
      sha: text(row.sha),
      subdir: text(row.subdir),
      version: text(row.version),
      requiresMoor: text(row.requiresMoor),
      tags,
      tools,
      hooks,
      platforms: strings(row.platforms),
      requirements: strings(kind === 'plugins' ? caps.requiresEnv : row.envVars),
      sourceUrl: webUrl(row.repo || row.sourceUrl),
      docsUrl: webUrl(row.docsUrl) || (text(row.docsPath)
        ? `${DOCS_ORIGIN}/docs/user-guide/skills/${text(row.docsPath)}`
        : null),
      stars: typeof row.stars === 'number' && Number.isFinite(row.stars) ? row.stars : null,
      search: [name, description, author, category, row.categoryLabel, source, ...tags, ...tools, ...hooks]
        .filter(Boolean).join(' ').toLowerCase()
    })
  }

  return [...entries.values()]
}

export async function fetchCatalog(kind: CatalogKind): Promise<CatalogEntry[]> {
  try {
    const response = await fetch(`${CATALOG_BASE}/${kind}.json`, {
      credentials: 'omit',
      signal: AbortSignal.timeout(10_000)
    })
    if (response.ok) {
      return parseCatalog(kind, await response.json())
    }
  } catch {
    // Fall back to mirror if primary endpoint is not available
  }

  const fallbackResponse = await fetch(`${FALLBACK_CATALOG_BASE}/${kind}.json`, {
    credentials: 'omit',
    signal: AbortSignal.timeout(60_000)
  })

  if (!fallbackResponse.ok) {
    throw new Error(`Catalog HTTP ${fallbackResponse.status}`)
  }

  return parseCatalog(kind, await fallbackResponse.json())
}

export function useCatalog(kind: CatalogKind, enabled = true) {
  return useQuery({
    queryKey: ['public-catalog', kind],
    // Re-enabling a mounted query retries errors even with retryOnMount off.
    // Keep failures parked until the user explicitly chooses Try again.
    enabled: query => enabled && query.state.status !== 'error',
    queryFn: () => fetchCatalog(kind),
    staleTime: 30 * 60_000,
    gcTime: Infinity,
    refetchOnWindowFocus: false,
    refetchOnReconnect: false,
    refetchOnMount: false,
    retryOnMount: false,
    retry: false
  })
}
