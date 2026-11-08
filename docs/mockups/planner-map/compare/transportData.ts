// Shared types, rules and helpers for the "Families without a car" layer (task T3).
import type { Records, Tract } from '../model'
import { COLORS, COMPARE_SEQ } from '../mapStyle'

export type Band = 'closer' | 'rough' | 'veryRough'

export interface TransportTract {
  pct: number | null
  households: number
  noCar: number
  moePct: number | null
  cv: number | null
  band: Band | null
}

export interface TransportData {
  source: string
  file: string
  rule: { z: number; cvCloser: number; cvVeryRough: number }
  bands: Record<Band | 'blank', number>
  tracts: Record<string, TransportTract>
}

// Class breaks, in percent of households with no car. Round numbers on purpose.
export const BREAKS = [5, 10, 15] as const
// "Many families without a car": the two darkest classes, so the cut is a legend break.
export const MANY = BREAKS[1]
export const CLASS_COLORS = COMPARE_SEQ.slice(0, BREAKS.length + 1)
// Stripe colors for very rough tracts: on the lightest class, and on the darker classes.
export const STRIPE_ON_LIGHT = COLORS.primary500
export const STRIPE_ON_DARK = '#FFFFFF'
// Feature-state key for the tract that "Show on map" points at.
export const FOCUS_STATE = 'transportFocus'

export const SOURCES = [
  { id: 'DS-X7b', label: 'ACS 2024 5-year B08201, households with no vehicle (Census Reporter)' },
  { id: 'F-1', label: 'CDC PLACES transport and food measures are blank for Florida' },
  { id: 'DS-X12', label: 'Second Harvest food finder sites (for "no site inside")' },
]

export const BAND_WORDS: Record<Band, string> = {
  closer: 'closer estimate',
  rough: 'rough estimate',
  veryRough: 'very rough guess',
}

const EMPTY: TransportData = {
  source: '',
  file: '',
  rule: { z: 1.645, cvCloser: 0, cvVeryRough: 0 },
  bands: { closer: 0, rough: 0, veryRough: 0, blank: 0 },
  tracts: {},
}

export function asData(extra: unknown): TransportData {
  if (extra && typeof extra === 'object' && 'tracts' in extra && 'rule' in extra)
    return extra as TransportData
  return EMPTY
}

export function classOf(pct: number): number {
  let i = 0
  while (i < BREAKS.length && pct >= BREAKS[i]!) i++
  return i
}

// "about 1 in 8" style wording. Returns null for a zero share. Shares below the first
// break are "fewer than 1 in 20", because "1 in 42" is hard to picture.
export function oneIn(pct: number): string | null {
  if (pct <= 0) return null
  if (pct < BREAKS[0]) return `fewer than 1 in ${Math.round(100 / BREAKS[0])}`
  const k = Math.round(100 / pct)
  return k <= 1 ? 'almost all' : `about 1 in ${k}`
}

export const capital = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)

// High need, a share at or above MANY, and no Second Harvest site inside the tract.
export function isCandidate(t: Tract, d: TransportTract | undefined): d is TransportTract {
  return t.cls === 'desert' && t.sitesInTract === 0 && d?.pct != null && d.pct >= MANY
}

export function summarize(records: Records, d: TransportData) {
  const classCounts = CLASS_COLORS.map(() => 0)
  const blank: string[] = []
  for (const t of records.tracts) {
    const v = d.tracts[t.geoid]
    if (!v || v.pct === null) blank.push(t.geoid)
    else if (t.drawn) classCounts[classOf(v.pct)]!++
  }
  const highNeed = records.tracts.filter((t) => t.cls === 'desert')
  const candidates = highNeed
    .filter((t) => isCandidate(t, d.tracts[t.geoid]))
    .map((t) => ({ t, v: d.tracts[t.geoid]! }))
    .sort((a, b) => (b.v.pct ?? 0) - (a.v.pct ?? 0))
  // Candidates whose share stays at or above MANY at the low end of the 90% range.
  const firmCandidates = candidates.filter((c) => (c.v.pct ?? 0) - (c.v.moePct ?? 0) >= MANY)
  const veryRoughDrawn = records.tracts.filter(
    (t) => t.drawn && d.tracts[t.geoid]?.band === 'veryRough',
  ).length
  const highNeedNoSite = highNeed.filter((t) => t.sitesInTract === 0).length
  return {
    classCounts,
    blank,
    highNeed,
    highNeedNoSite,
    candidates,
    firmCandidates,
    veryRoughDrawn,
  }
}
