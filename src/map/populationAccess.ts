import type { TractRecord } from '../wizard/alignmentWizard'
import { MAX_REACH_MILES, REACH_STEP_MILES } from './reach'
import { reachMinutes } from './proximity'

export const ACCESS_POPULATION_SHARE = 0.8

export type PopulationAccess =
  | { readonly status: 'estimated' | 'beyond'; readonly minutes: number }
  | { readonly status: 'unavailable' }

/** Use the first prepared radius covering 80% of residents, retaining the existing time conversion. */
export function populationAccess(
  tract: Pick<TractRecord, 'pop2020' | 'reach_share' | 'nearest_block_miles'>,
): PopulationAccess {
  if (
    tract.pop2020 <= 0 ||
    tract.nearest_block_miles === null ||
    tract.reach_share.length !== MAX_REACH_MILES / REACH_STEP_MILES + 1
  )
    return { status: 'unavailable' }
  let previous = 0
  for (const share of tract.reach_share) {
    if (share === null || !Number.isFinite(share) || share < previous || share > 1)
      return { status: 'unavailable' }
    previous = share
  }
  const index = tract.reach_share.findIndex(
    (share) => share !== null && share >= ACCESS_POPULATION_SHARE,
  )
  if (index < 0) return { status: 'beyond', minutes: reachMinutes(MAX_REACH_MILES) }
  return { status: 'estimated', minutes: reachMinutes(index * REACH_STEP_MILES) }
}

export function populationAccessText(access: PopulationAccess): string {
  if (access.status === 'unavailable') return 'No data'
  if (access.status === 'beyond') return `Over ${access.minutes} min`
  return access.minutes === 0 ? 'Under 1 min' : `${Math.ceil(access.minutes)} min`
}
