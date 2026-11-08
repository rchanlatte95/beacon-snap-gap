// Data and helpers for the "Where our data has gaps" Compare-with layer (task T4).
// See blindspots.ts for the rules. Kept apart from the Panel component for fast refresh.
import type { Records } from '../model'
import { GROUP_QUARTERS_PCT, SMALL_HOUSEHOLDS } from '../model'
import { COMPARE_SEQ, hatchImage } from '../mapStyle'

export type GapLevel = 'none' | 'some' | 'big'

// Plain names for the source indicator names in records.standin.json (make-standin.mjs).
// An indicator that is not in this list is shown with its source name, so it is never hidden.
export const PLAIN_NAME: Record<string, string> = {
  'Poverty rate (ACS S1701)': 'how many people live in poverty',
  'SNAP households (ACS S2201)': 'how many families get SNAP',
  'Low income, low access, driving distance (USDA SRAM)':
    'if families here have low income and live far from a grocery store',
  'No-vehicle households (ACS B08201)': 'how many homes have no car',
  'Food stamps, adults (CDC PLACES)': 'how many adults say they get food stamps',
  'Food insecurity (CDC PLACES)': 'how many adults say they do not have enough food',
  'Lack of transportation (CDC PLACES)': 'how many adults say they cannot get a ride',
  'FEMA National Risk Index rating': 'the risk of storms, floods and other disasters',
}
export const plain = (m: string) => PLAIN_NAME[m] ?? m

// The two class inputs (POST-CLS-2). When one is blank the tract is Insufficient data.
export const CORE = /S1701|SRAM/

export const LEVEL_LABEL: Record<GapLevel, string> = {
  none: 'Only the region-wide gaps',
  some: 'Some facts missing or less sure',
  big: 'Key facts missing',
}
export const LEVELS: GapLevel[] = ['none', 'some', 'big']
export const FILL: Record<Exclude<GapLevel, 'big'>, string> = {
  none: COMPARE_SEQ[0],
  some: COMPARE_SEQ[2],
}
export const HATCH_ID = 'blindspots-hatch'
export const FILL_LAYER = 'blindspots-fill'
export const BIG_LAYER = 'blindspots-big'
export const NEED_LAYER = 'blindspots-need-line'

export interface TractGaps {
  level: GapLevel
  // Missing indicators for this tract only (not region-wide).
  own: string[]
  fewHomes: boolean
  groupQuarters: boolean
}

export interface Summary {
  regionWide: string[]
  byGeoid: Map<string, TractGaps>
}

// Region-wide = blank in every tract. Computed from the data, not a fixed list.
const cache = new WeakMap<Records, Summary>()
export function summarize(r: Records): Summary {
  const hit = cache.get(r)
  if (hit) return hit
  const blanks = new Map<string, number>()
  for (const t of r.tracts) for (const m of t.missing) blanks.set(m, (blanks.get(m) ?? 0) + 1)
  const regionWide = [...blanks].filter(([, c]) => c === r.tracts.length).map(([m]) => m)
  const byGeoid = new Map<string, TractGaps>()
  for (const t of r.tracts) {
    const own = t.missing.filter((m) => !regionWide.includes(m))
    // Same tests and thresholds as limits() in model.ts (confidence rule A).
    const fewHomes = (t.households ?? 0) < SMALL_HOUSEHOLDS
    const groupQuarters = (t.groupQuartersPct ?? 0) > GROUP_QUARTERS_PCT
    const level: GapLevel =
      t.cls === 'insufficient' || own.some((m) => CORE.test(m))
        ? 'big'
        : own.length > 0 || fewHomes || groupQuarters
          ? 'some'
          : 'none'
    byGeoid.set(t.geoid, { level, own, fewHomes, groupQuarters })
  }
  const s = { regionWide, byGeoid }
  cache.set(r, s)
  return s
}

export function listText(items: string[]) {
  if (items.length <= 1) return items.join('')
  return `${items.slice(0, -1).join(', ')} and ${items.at(-1)}`
}

export const allPlaces = (ms: string[]) => ms.length > 0 && ms.every((m) => m.includes('CDC PLACES'))

// Legend swatch for the worst level, drawn from the same hatch image as the map.
let hatchUrl: string | null = null
export function hatchSwatch(): string {
  if (hatchUrl !== null) return hatchUrl
  const img = hatchImage()
  const canvas = document.createElement('canvas')
  canvas.width = img.width
  canvas.height = img.height
  const c2d = canvas.getContext('2d')
  if (!c2d) return ''
  c2d.putImageData(new ImageData(new Uint8ClampedArray(img.data), img.width, img.height), 0, 0)
  hatchUrl = `url(${canvas.toDataURL()})`
  return hatchUrl
}
