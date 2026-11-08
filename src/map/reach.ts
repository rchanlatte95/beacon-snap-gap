import type { TractRecord } from '../wizard/alignmentWizard'

// REQ-56, REQ-64 (Z-2 2-A): the Build writes reach for every step; the App only reads it.
export const REACH_STEP_MILES = 0.5
export const MAX_REACH_MILES = 20
export const DEFAULT_REACH_MILES = 10

type ReachRecord = Pick<
  TractRecord,
  'pop2020' | 'reach_share' | 'reach_sites' | 'nearest_block_miles'
>

export interface ReachFacts {
  readonly miles: number
  /** Share of the tract's 2020 block population within `miles` of a site; null when nobody lives there. */
  readonly share: number | null
  readonly sites: number
  readonly peoplePerSite: number | null
  /** Whether the closest populated block is within `miles`; null when the tract has no distance data. */
  readonly within: boolean | null
}

/** The step a requested distance selects: 0 to 20 miles, nearest 0.5. A non-number gives the start value. */
export function reachMiles(requested: number): number {
  if (!Number.isFinite(requested)) return DEFAULT_REACH_MILES
  const clamped = Math.min(MAX_REACH_MILES, Math.max(0, requested))
  return Math.round(clamped / REACH_STEP_MILES) * REACH_STEP_MILES
}

export function reachFacts(tract: ReachRecord, requested: number): ReachFacts {
  const miles = reachMiles(requested)
  const step = Math.round(miles / REACH_STEP_MILES)
  const sites = tract.reach_sites[step] ?? 0
  return {
    miles,
    share: tract.reach_share[step] ?? null,
    sites,
    peoplePerSite: sites > 0 ? Math.round(tract.pop2020 / sites) : null,
    within: tract.nearest_block_miles === null ? null : tract.nearest_block_miles <= miles,
  }
}

/** Splits a group into the tracts beyond the distance, the count within it, and those with no distance data. */
export function splitByReach<T extends ReachRecord>(tracts: readonly T[], miles: number) {
  const beyond: T[] = []
  const unknown: T[] = []
  let withinCount = 0
  for (const tract of tracts) {
    const within = reachFacts(tract, miles).within
    if (within === null) unknown.push(tract)
    else if (within) withinCount++
    else beyond.push(tract)
  }
  return { beyond, unknown, withinCount }
}

export function milesText(miles: number): string {
  return `${miles} ${miles === 1 ? 'mile' : 'miles'}`
}
